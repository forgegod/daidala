from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import daidala.artifact_curator as artifact_curator_module
from daidala.archive_io import ArchiveError
from daidala.artifact_access import ArtifactAccessError, ArtifactAccessService, ArtifactAvailability
from daidala.artifact_curator import (
    ArtifactCurator,
    ArtifactCuratorStore,
    CurationRow,
    CurationState,
    CuratorDocument,
    CuratorError,
    CuratorPolicy,
)
from daidala.kanban import KanbanCardStatus
from daidala.service import WorkflowService
from daidala.state import (
    ArtifactReference,
    CardReference,
    SkillDigest,
    StageProfile,
    WorkflowLedger,
    WorkflowStage,
)
from daidala.store import WorkflowStore
from daidala.workflow import new_workflow

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _profiles() -> tuple[StageProfile, ...]:
    return tuple(
        StageProfile(stage=stage, profile="worker")
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    )


def _write(root: Path, relative: str, content: bytes) -> ArtifactReference:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    stage = WorkflowStage.DELIVER if path.name == "delivery.json" else WorkflowStage.PLAN
    return ArtifactReference(
        stage=stage,
        plan_revision=0,
        path=str(path.resolve()),
        digest=_digest(content),
        recorded_at=NOW,
        policy_revision=0,
    )


def _ledger(
    store: WorkflowStore,
    workflow_id: str,
    *,
    delivered: bool = True,
    owned_worktree: bool = False,
    with_card: bool = False,
) -> WorkflowLedger:
    artifact_root = store.data_root / "workflows" / workflow_id / "artifacts"
    plan = _write(artifact_root, "policy-0000/plan-0000/plan.md", b"# Plan\n")
    artifacts = [plan]
    if delivered:
        artifacts.append(
            _write(
                artifact_root,
                "policy-0000/plan-0000/delivery.json",
                b'{"committed":false,"pushed":false}\n',
            )
        )
    supplemental = artifact_root / "policy-0000/plan-0000/implementation-paths.json"
    supplemental.write_text('{"changed_paths":["private-name.txt"]}\n', encoding="utf-8")
    ledger = new_workflow(
        workflow_id=workflow_id,
        board_slug="daidala-test",
        target_repository=str((store.data_root / "target").resolve()),
        baseline_commit="a" * 40,
        requested_goal="Exercise deterministic artifact curation",
        pack_name="addyosmani",
        pack_source_revision="b" * 40,
        skill_digests=(SkillDigest(name="interview-me", digest="c" * 64),),
        stage_profiles=_profiles(),
        created_at=NOW,
    )
    cards = ()
    if with_card:
        cards = (
            CardReference(
                stage=WorkflowStage.PLAN,
                plan_revision=0,
                task_id=f"task-{workflow_id}",
                idempotency_key=f"key-{workflow_id}",
                board_slug="daidala-test",
                policy_revision=0,
            ),
        )
    worktree = str((store.data_root / "worktree").resolve()) if owned_worktree else None
    return replace(
        ledger,
        artifacts=tuple(artifacts),
        card_references=cards,
        worktree_path=worktree,
        worktree_owned=owned_worktree,
        updated_at=NOW,
    )


def _configured_curator(
    store: WorkflowStore,
    clock: list[datetime],
    *,
    status_provider=None,
    fault_injector=None,
) -> ArtifactCurator:
    curator = ArtifactCurator(
        store,
        clock=lambda: clock[0],
        status_provider=status_provider,
        fault_injector=fault_injector,
    )
    initial = curator.status()
    curator.configure(
        CuratorPolicy(enabled=True, stale_after_days=30, archive_after_days=90),
        expected_state_digest=initial.state_digest,
    )
    return curator


def _apply(curator: ArtifactCurator, preview) -> object:
    if preview.operation == "run":
        return curator.apply_run(expected_preview_digest=preview.digest)
    if preview.operation in {"pin", "unpin"}:
        return curator.apply_pin(
            preview.workflow_id,
            pinned=preview.operation == "pin",
            expected_preview_digest=preview.digest,
        )
    if preview.operation == "archive":
        return curator.apply_archive(
            preview.workflow_id,
            expected_preview_digest=preview.digest,
        )
    if preview.operation == "restore":
        return curator.apply_restore(
            preview.workflow_id,
            preview.archive_id,
            expected_preview_digest=preview.digest,
        )
    raise AssertionError(f"unknown preview operation: {preview.operation}")


def test_state_is_strict_private_bounded_and_compare_and_swap(tmp_path: Path) -> None:
    data_root = (tmp_path / "profile-a" / "daidala").resolve()
    data_root.mkdir(parents=True)
    state = ArtifactCuratorStore(data_root)

    initial = state.read()
    assert initial.policy.enabled is False
    configured = state.replace(
        replace(
            initial,
            policy=CuratorPolicy(enabled=True, stale_after_days=10, archive_after_days=20),
        ),
        expected_digest=initial.digest,
    )

    assert state.path.stat().st_mode & 0o777 == 0o600
    assert state.read() == configured
    with pytest.raises(CuratorError, match="concurrently"):
        state.replace(initial, expected_digest=initial.digest)

    payload = configured.to_dict()
    payload["unexpected"] = True
    state.path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(state.path, 0o600)
    with pytest.raises(CuratorError, match="schema"):
        state.read()

    state.path.write_text(
        '{"schema":"daidala.artifact-curator/v1","schema":"duplicate"}\n',
        encoding="utf-8",
    )
    os.chmod(state.path, 0o600)
    with pytest.raises(CuratorError, match="schema"):
        state.read()

    with pytest.raises(CuratorError, match="exceed"):
        CuratorDocument(
            rows=tuple(
                CurationRow(
                    workflow_id=f"{index:04}-" + "x" * 123,
                    state=CurationState.ACTIVE,
                    first_terminal_observed_at=None,
                    last_transition_at=NOW,
                    pinned=False,
                )
                for index in range(4096)
            )
        ).canonical_bytes()
    with pytest.raises(CuratorError, match="archive age"):
        CuratorPolicy(enabled=True, stale_after_days=30, archive_after_days=30)


@pytest.mark.parametrize(
    "values",
    [
        {"enabled": 1},
        {"stale_after_days": 0},
        {"archive_after_days": 3651},
        {"stale_after_days": 30, "archive_after_days": 30},
    ],
)
def test_curator_policy_rejects_invalid_bounds(values: dict[str, object]) -> None:
    with pytest.raises(CuratorError):
        CuratorPolicy(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("delivered", "owned_worktree", "card_status", "expected"),
    [
        (True, False, None, "observe"),
        (True, True, None, None),
        (False, False, "done", None),
        (False, False, "archived", "observe"),
        (False, False, "blocked", None),
        (False, False, "running", None),
    ],
)
def test_terminal_classification_fails_closed(
    tmp_path: Path,
    delivered: bool,
    owned_worktree: bool,
    card_status: str | None,
    expected: str | None,
) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-terminal"
    ledger = _ledger(
        store,
        workflow_id,
        delivered=delivered,
        owned_worktree=owned_worktree,
        with_card=not delivered,
    )
    store.create(ledger)

    def statuses(selected: WorkflowLedger) -> tuple[KanbanCardStatus, ...]:
        if card_status is None:
            raise RuntimeError("Kanban unavailable")
        card = selected.card_references[0]
        return (KanbanCardStatus(card.stage, card.task_id, card_status, "worker"),)

    curator = _configured_curator(store, [NOW], status_provider=statuses)
    actions = curator.preview_run().actions
    assert (actions[0].action if actions else None) == expected


def test_pending_revision_request_blocks_delivered_eligibility(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "data")
    curator = ArtifactCurator(store, clock=lambda: NOW)
    ledger = cast(
        WorkflowLedger,
        SimpleNamespace(
            worktree_owned=False,
            worktree_path=None,
            pending_revision_request=object(),
            artifact_for=lambda _stage: object(),
        ),
    )

    assert curator._terminal_eligible(ledger) is False


def test_age_transitions_and_pinning_are_deterministic(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-age"
    store.create(_ledger(store, workflow_id))
    clock = [NOW]
    curator = _configured_curator(store, clock)

    observed = curator.preview_run()
    assert [action.action for action in observed.actions] == ["observe"]
    _apply(curator, observed)
    assert curator.status().rows[0].state is CurationState.ACTIVE

    clock[0] = NOW + timedelta(days=30)
    stale = curator.preview_run()
    assert [action.action for action in stale.actions] == ["mark-stale"]
    _apply(curator, stale)
    assert curator.status().rows[0].state is CurationState.STALE

    pinned = curator.preview_pin(workflow_id, pinned=True)
    _apply(curator, pinned)
    clock[0] = NOW + timedelta(days=90)
    assert curator.preview_run().actions == ()

    unpinned = curator.preview_pin(workflow_id, pinned=False)
    _apply(curator, unpinned)
    ready = curator.preview_run()
    assert [action.action for action in ready.actions] == ["archive"]


def test_pin_before_first_observation_blocks_automatic_curation(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-pinned-before-observation"
    store.create(_ledger(store, workflow_id))
    curator = _configured_curator(store, [NOW])

    _apply(curator, curator.preview_pin(workflow_id, pinned=True))

    assert curator.preview_run().actions == ()
    row = curator.status().rows[0]
    assert row.pinned is True
    assert row.first_terminal_observed_at is None


def test_missing_ledger_evidence_is_not_observed_as_terminal(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-missing-evidence"
    ledger = _ledger(store, workflow_id)
    store.create(ledger)
    Path(ledger.artifacts[0].path).unlink()
    curator = _configured_curator(store, [NOW])

    assert curator.preview_run().actions == ()
    assert curator.status().rows == ()


@pytest.mark.parametrize(
    "boundary",
    [
        "after-archive-publish",
        "after-manifest-publish",
        "after-state-publish",
        "after-source-remove",
    ],
)
def test_interruption_at_mutation_boundaries_preserves_a_verified_copy(
    tmp_path: Path, boundary: str
) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = f"wf-fault-{boundary}"
    store.create(_ledger(store, workflow_id))
    fired = False

    def fail(selected: str) -> None:
        nonlocal fired
        if selected == boundary and not fired:
            fired = True
            raise RuntimeError("injected curator interruption")

    curator = _configured_curator(store, [NOW], fault_injector=fail)
    preview = curator.preview_archive(workflow_id)
    with pytest.raises(RuntimeError, match="injected"):
        _apply(curator, preview)

    access = ArtifactAccessService(store, archive_lookup=curator.archive_lookup)
    entries = access.list(workflow_id)
    assert entries
    assert all(entry.availability is not ArtifactAvailability.MISSING for entry in entries)
    if boundary in {"after-archive-publish", "after-manifest-publish"}:
        assert all(entry.availability is ArtifactAvailability.ACTIVE for entry in entries)
    elif boundary == "after-state-publish":
        assert all(
            entry.availability is ArtifactAvailability.ACTIVE_AND_ARCHIVED
            for entry in entries
        )
    else:
        assert {entry.availability for entry in entries} == {
            ArtifactAvailability.ACTIVE_AND_ARCHIVED,
            ArtifactAvailability.ARCHIVED,
        }
    for entry in entries:
        assert access.read_text(workflow_id, entry.artifact_id).content

    retry = curator.preview_archive(workflow_id)
    _apply(curator, retry)
    archived = access.list(workflow_id)
    assert all(entry.availability is ArtifactAvailability.ARCHIVED for entry in archived)
    assert curator.list_archived()[0]["workflow_id"] == workflow_id
    replay = curator.preview_archive(workflow_id)
    assert replay.actions == ()
    assert curator.apply_archive(
        workflow_id, expected_preview_digest=replay.digest
    ).replayed is True


def test_archive_creation_failure_preserves_all_active_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-create-failure"
    ledger = _ledger(store, workflow_id)
    store.create(ledger)
    curator = _configured_curator(store, [NOW])
    preview = curator.preview_archive(workflow_id)

    def fail_create(*_args, **_kwargs):
        raise ArchiveError("archive create")

    monkeypatch.setattr(artifact_curator_module, "create_archive", fail_create)

    with pytest.raises(CuratorError, match="creation failed"):
        curator.apply_archive(workflow_id, expected_preview_digest=preview.digest)
    assert all(Path(reference.path).exists() for reference in ledger.artifacts)
    assert curator.list_archived() == ()


def test_cleanup_rejects_same_size_source_change_after_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-source-drift"
    ledger = _ledger(store, workflow_id)
    store.create(ledger)
    curator = _configured_curator(store, [NOW])
    source = Path(ledger.artifacts[0].path)
    real_digest = artifact_curator_module._file_digest
    changed = False

    def digest_then_change(path: Path, *, expected=None):
        nonlocal changed
        result = real_digest(path, expected=expected)
        if path == source and expected is not None and not changed:
            changed = True
            path.write_bytes(b"!" * result[1])
        return result

    monkeypatch.setattr(artifact_curator_module, "_file_digest", digest_then_change)

    with pytest.raises(CuratorError, match="source drift"):
        _apply(curator, curator.preview_archive(workflow_id))
    assert source.exists()
    assert source.read_bytes() == b"!" * len(b"# Plan\n")


def test_ledger_change_after_state_publication_rearchives_before_cleanup(
    tmp_path: Path,
) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-state-publication-race"
    store.create(_ledger(store, workflow_id))
    fired = False

    def fail_after_state(boundary: str) -> None:
        nonlocal fired
        if boundary == "after-state-publish" and not fired:
            fired = True
            raise RuntimeError("injected after state publication")

    curator = _configured_curator(store, [NOW], fault_injector=fail_after_state)
    first_preview = curator.preview_archive(workflow_id)
    with pytest.raises(RuntimeError, match="injected"):
        _apply(curator, first_preview)

    observed = store.get_with_token(workflow_id)
    store.update(
        replace(observed.ledger, updated_at=NOW + timedelta(seconds=1)),
        expected_updated_at=observed.updated_at,
    )
    second_preview = curator.preview_archive(workflow_id)
    assert second_preview.archive_id != first_preview.archive_id

    _apply(curator, second_preview)

    row = curator.status().rows[0]
    assert len(row.archive_ids) == 2
    assert all(
        entry.availability is ArtifactAvailability.ARCHIVED
        for entry in ArtifactAccessService(
            store, archive_lookup=curator.archive_lookup
        ).list(workflow_id)
    )


def test_archive_verification_cache_revalidates_once_per_unchanged_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-verification-cache"
    store.create(_ledger(store, workflow_id))
    curator = _configured_curator(store, [NOW])
    _apply(curator, curator.preview_archive(workflow_id))
    curator._manifest_cache.clear()
    real_verify = artifact_curator_module.verify_archive
    calls = 0

    def counted_verify(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_verify(*args, **kwargs)

    monkeypatch.setattr(artifact_curator_module, "verify_archive", counted_verify)
    access = ArtifactAccessService(store, archive_lookup=curator.archive_lookup)
    entries = access.list(workflow_id)
    for entry in entries:
        access.read_text(workflow_id, entry.artifact_id)

    assert calls == 1


def test_archive_lookup_tamper_restore_collision_and_safe_restore_root(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-restore"
    ledger = _ledger(store, workflow_id)
    historical_plan = Path(ledger.artifact_for(WorkflowStage.PLAN).path)  # type: ignore[union-attr]
    store.create(ledger)
    curator = _configured_curator(store, [NOW])

    _apply(curator, curator.preview_archive(workflow_id))
    archived = curator.list_archived()[0]
    archive_id = archived["archive_id"]
    assert not historical_plan.exists()

    restore = curator.preview_restore(workflow_id, archive_id)
    result = _apply(curator, restore)
    restored_plan = (
        store.data_root
        / "artifact-restores"
        / workflow_id
        / archive_id
        / "policy-0000/plan-0000/plan.md"
    )
    assert restored_plan.read_bytes() == b"# Plan\n"
    assert not historical_plan.exists()
    row = curator.status().rows[0]
    assert row.state is CurationState.ACTIVE
    assert row.pinned is True
    assert result.to_dict()["restored_files"] == archived["member_count"]

    restored_plan.write_text("conflict\n", encoding="utf-8")
    with pytest.raises(CuratorError, match="restore failed") as raised:
        _apply(curator, curator.preview_restore(workflow_id, archive_id))
    assert "plan.md" not in str(raised.value)
    assert str(store.data_root) not in str(raised.value)

    archive_path = store.data_root / "artifact-archives" / workflow_id / f"{archive_id}.tar.gz"
    archive_path.write_bytes(b"tampered")
    access = ArtifactAccessService(store, archive_lookup=curator.archive_lookup)
    with pytest.raises(ArtifactAccessError, match="archive"):
        access.list(workflow_id)


def test_restore_rechecks_ledger_before_publishing_active_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-restore-ledger-race"
    store.create(_ledger(store, workflow_id))
    curator = _configured_curator(store, [NOW])
    _apply(curator, curator.preview_archive(workflow_id))
    archive_id = str(curator.list_archived()[0]["archive_id"])
    preview = curator.preview_restore(workflow_id, archive_id)
    real_restore = artifact_curator_module.restore_archive

    def restore_then_change_ledger(*args, **kwargs):
        result = real_restore(*args, **kwargs)
        observed = store.get_with_token(workflow_id)
        store.update(
            replace(observed.ledger, updated_at=NOW + timedelta(seconds=1)),
            expected_updated_at=observed.updated_at,
        )
        return result

    monkeypatch.setattr(
        artifact_curator_module,
        "restore_archive",
        restore_then_change_ledger,
    )

    with pytest.raises(CuratorError, match="changed during artifact restore"):
        curator.apply_restore(
            workflow_id,
            archive_id,
            expected_preview_digest=preview.digest,
        )
    assert curator.status().rows[0].state is CurationState.ARCHIVED


def test_lock_contention_and_cross_profile_isolation(tmp_path: Path) -> None:
    first_store = WorkflowStore(tmp_path / "profile-a" / "daidala")
    second_store = WorkflowStore(tmp_path / "profile-b" / "daidala")
    first_store.create(_ledger(first_store, "wf-a"))
    second_store.create(_ledger(second_store, "wf-b"))
    first = _configured_curator(first_store, [NOW])
    second = _configured_curator(second_store, [NOW])

    descriptor = os.open(first.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(CuratorError, match="lock contention"):
            _apply(first, first.preview_archive("wf-a"))
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    workflow_descriptor = os.open(first._workflow_lock("wf-a"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(workflow_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(CuratorError, match="lock contention"):
            _apply(first, first.preview_archive("wf-a"))
    finally:
        fcntl.flock(workflow_descriptor, fcntl.LOCK_UN)
        os.close(workflow_descriptor)

    _apply(second, second.preview_archive("wf-b"))
    assert second.list_archived()[0]["workflow_id"] == "wf-b"
    assert first.list_archived() == ()


def test_curator_lock_refuses_symlink_without_touching_its_target(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "data")
    curator = ArtifactCurator(store, clock=lambda: NOW)
    target = tmp_path / "unrelated-private-file"
    target.write_text("preserve\n", encoding="utf-8")
    os.chmod(target, 0o640)
    curator.lock_path.symlink_to(target)
    initial = curator.status()

    with pytest.raises(CuratorError, match="lock is unsafe"):
        curator.configure(
            CuratorPolicy(enabled=True),
            expected_state_digest=initial.state_digest,
        )

    assert target.read_text(encoding="utf-8") == "preserve\n"
    assert target.stat().st_mode & 0o777 == 0o640


def test_workflow_service_wires_curator_archives_into_exact_artifact_access(
    tmp_path: Path,
) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-service"
    store.create(_ledger(store, workflow_id))
    service = WorkflowService(store, clock=lambda: NOW)
    before = service.list_artifacts(workflow_id)
    expected = {
        entry.artifact_id: service.read_artifact_text(workflow_id, entry.artifact_id).content
        for entry in before
    }

    preview = service.preview_curator_archive(workflow_id)
    service.apply_curator_archive(
        workflow_id,
        expected_preview_digest=preview.digest,
    )

    entries = service.list_artifacts(workflow_id)
    assert entries
    assert [(entry.artifact_id, entry.digest) for entry in entries] == [
        (entry.artifact_id, entry.digest) for entry in before
    ]
    assert all(entry.availability is ArtifactAvailability.ARCHIVED for entry in entries)
    assert {
        entry.artifact_id: service.read_artifact_text(workflow_id, entry.artifact_id).content
        for entry in entries
    } == expected


def test_stale_ledger_preview_preserves_active_sources(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "wf-ledger-race"
    store.create(_ledger(store, workflow_id))
    curator = _configured_curator(store, [NOW])
    preview = curator.preview_archive(workflow_id)

    observed = store.get_with_token(workflow_id)
    store.update(
        replace(observed.ledger, updated_at=NOW + timedelta(seconds=1)),
        expected_updated_at=observed.updated_at,
    )

    with pytest.raises(CuratorError, match="preview"):
        curator.apply_archive(workflow_id, expected_preview_digest=preview.digest)
    assert all(
        Path(reference.path).exists() for reference in store.get(workflow_id).artifacts
    )
    assert curator.list_archived() == ()


def test_path_unsafe_workflow_identity_fails_before_curation(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "data")
    safe = _ledger(store, "wf-safe")
    store.create(replace(safe, workflow_id="../escape"))
    curator = _configured_curator(store, [NOW])

    with pytest.raises(CuratorError, match="workflow ID"):
        curator.preview_run()
    assert not (tmp_path / "escape").exists()


def test_disabled_policy_does_not_create_or_mutate_curator_state(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "data")
    store.create(_ledger(store, "wf-disabled"))
    curator = ArtifactCurator(store, clock=lambda: NOW)

    preview = curator.preview_run()
    assert preview.actions == ()
    assert curator.apply_run(expected_preview_digest=preview.digest).replayed is True
    assert curator.status().rows == ()
    assert not curator.state_store.path.exists()
