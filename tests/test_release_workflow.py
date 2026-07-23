from pathlib import Path

RELEASE_WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "release.yml"


def test_live_probe_runs_only_for_tags_and_manual_dispatch() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    job = workflow.split("  hermes-compatibility:\n", 1)[1]

    assert "if: github.event_name == 'workflow_dispatch' || startsWith(" in job
    assert "github.ref, 'refs/tags/v'" in job
    assert "needs: [test, package]" in job
    assert 'node-version: "22"' in job
    assert "git -C /tmp/hermes-agent checkout 4281151ae859241351ba14d8c7682dc67ff4c126" in job
    assert (
        "git -C /tmp/hermes-agent update-ref refs/remotes/origin/main "
        "4281151ae859241351ba14d8c7682dc67ff4c126"
    ) in job
    assert (
        "git -C /tmp/hermes-agent remote set-url origin "
        "file:///tmp/hermes-agent-pinned-origin"
    ) in job
    assert "npm ci --workspace web && npm run build -w web" in job
    assert "python scripts/run_hermes_support_matrix.py" in job
    assert "--host supported-v0182 0.18.2 2026.7.7.2 4281151a" in job
    assert "python -m pip install -e ." not in job
    assert "github.event_name == 'push'" not in job
    assert "github.event_name == 'pull_request'" not in job


def test_release_workflow_checks_and_hashes_one_exact_wheel_before_matrix() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    package = workflow.split("  package:\n", 1)[1].split(
        "  hermes-compatibility:\n", 1
    )[0]
    compatibility = workflow.split("  hermes-compatibility:\n", 1)[1]

    assert "actions/upload-artifact@v6" in package
    assert "name: daidala-dist" in package
    assert "actions/download-artifact@v6" in compatibility
    assert 'test "${#wheels[@]}" -eq 1' in compatibility
    hash_index = compatibility.index('wheel_sha256="$(sha256sum')
    matrix_index = compatibility.index("python scripts/run_hermes_support_matrix.py")
    assert hash_index < matrix_index
    assert '--expected-wheel-sha256 "$wheel_sha256"' in compatibility
