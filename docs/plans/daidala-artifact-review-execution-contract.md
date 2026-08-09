# Daidala artifact review execution contract

**Contract ID:** daidala-artifact-review

**Created:** 2026-07-24

**Used by:** [P0205 artifact access core](P0205-daidala-artifact-access-core.md),
[P0300 artifact CLI](P0300-daidala-artifact-access-and-cli.md),
[P0310 artifact curation](P0310-daidala-artifact-curation.md), and
[P0320 artifact dashboard, cron, and verification](P0320-daidala-artifact-dashboard-cron-and-verification.md).

This repository-tracked document owns the pinned cross-unit risk and detailed
implementation contracts for the artifact-review plan family. It is not an
executable plan and carries no execution slot, progress state, findings ledger,
or approval authority. The linked active plans own dependencies, findings,
phase gates, and progress; execution reads only their exact linked headings.

Daidala will expose ledger-bound workflow evidence through exact-ID CLI and authenticated dashboard review surfaces, and will move old terminal-workflow artifact files into verified, restorable profile-local archives without changing policy-ledger identity or introducing automatic deletion.

## Current state

- Workflow status returns the complete policy ledger, including artifact paths and SHA-256 digests, but there is no `artifacts list`, `show`, or `export` command (`daidala/cli.py:701-722`, `daidala/state.py:338-372`).
- Runtime data resolves through the active Hermes home/profile and the CLI constructs `WorkflowStore` below `<resolved-data-root>/daidala`; no implementation may hard-code `~/.hermes` (`daidala/locations.py:33-52`, `daidala/cli.py:887-903`).
- Revision-addressed stage evidence currently lives below `<profile-data-root>/daidala/workflows/<workflow-id>/artifacts/`; historical paths and digests are immutable evidence (`docs/15-self-improvement.md:211-227`, `docs/16-self-improvement-setup.md:123-145`).
- The optional dashboard is a profile-safe read model and deliberately refuses arbitrary filesystem reads. Its pending approval item currently renders generic rationale but neither the plan body nor the complete tuple, so the user cannot make an informed approval from the browser (`daidala/dashboard_backend.py:466-481`, `dashboard/dist/index.js:149-166`).
- Delivery releases the owned detached worktree after writing reviewed evidence, so completed review must use captured artifacts rather than a surviving mutable checkout (`daidala/service.py:656-721`).
- Hermes Curator provides a useful lifecycle model—deterministic `active → stale → archived`, pinning, pre-mutation backup, restore, and no automatic deletion—but it is scoped to Hermes skills and is not a public artifact-storage API ([official Curator documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/curator)). Daidala must reuse the design, not import Hermes private curator modules or invoke the skill curator against workflow files.
- The shared archive plan owns policy-neutral verified tar/gzip I/O
  (`P0100-daidala-shared-archive-io.md`). The dashboard plan consumes it for
  checkout backups ([P0220](P0220-daidala-dashboard-checkouts-and-project-links.md));
  this plan consumes it for workflow artifact archives. Neither dependent plan
  may introduce a second tar implementation.

## Risk call-out

Current ledger references contain absolute artifact paths. Moving bytes first would leave apparently valid ledger paths pointing at missing files and would violate the existing historical-evidence contract. The safety order is therefore mandatory: land a ledger-owned resolver and exact-ID access surface first; archive only terminal workflows; create and verify an immutable archive manifest before removing any source file; retain the original ledger unchanged; and make archived availability explicit in the read projection. A failed or interrupted archive must leave either verified active bytes, a verified archive, or both—never neither.

Workflow artifacts and verification output may contain credentials, private paths, or other sensitive content. Archive directories use mode `0700`; archive, manifest, restored, and exported files use mode `0600`; content is never written to logs, Kanban comments, cron output, or unauthenticated responses. Curator inventory and errors report workflow IDs, counts, digests, and classified states only.

## Execution-unit map

| Contract sections | Active plan | Purpose |
|---|---|---|
| Phase 0 | [P0205](P0205-daidala-artifact-access-core.md) | Ledger-owned resolver required before dashboard plan approval |
| Phase 1 | [P0300](P0300-daidala-artifact-access-and-cli.md) | Native/standalone review/export commands |
| Phase 2 | [P0310](P0310-daidala-artifact-curation.md) | Deterministic archive, pin, restore, and failure recovery |
| Phases 3–5 | [P0320](P0320-daidala-artifact-dashboard-cron-and-verification.md) | Authenticated dashboard controls, opt-in cron, docs, package, and full verification |

## Phase 0 — Add the ledger-owned artifact catalog and resolver

**Goal:** Give every review surface one profile-safe service that enumerates only active ledger-owned evidence and resolves verified bytes while preserving immutable ledger identity; the first consumer is the dashboard's current-plan approval gate.

**Steps:**

1. Define the exact user-facing artifact selector as an opaque deterministic
   `artifact_id` derived from reference kind, workflow ID, policy revision, plan
   revision, stage/evidence kind, and recorded SHA-256 digest. Do not add
   `current`, `latest`, basename-only, or arbitrary-path selectors.
2. Add `daidala/artifact_access.py` with frozen projections for `ArtifactId`, `ArtifactAvailability`, and `ArtifactCatalogEntry`. Catalog only:
   - `WorkflowLedger.artifacts` stage references;
   - `WorkflowLedger.verification_evidence` output references;
   - constraint and activation references already carrying an exact path and digest when explicitly requested by kind.
3. Keep ledger `path` and `digest` unchanged as provenance. Add active availability as a read projection without rewriting policy-ledger rows during list/show/export.
4. Resolve active files only after proving the path is beneath the exact workflow artifact root, is a direct regular file, has no symlink component, satisfies the existing document bound, and hashes to the ledger digest. Never accept a caller-provided filesystem path.
5. Treat files that exist below the workflow artifact directory but lack a ledger reference as non-review evidence. `list/read_text/export` must not elevate them into ledger-bound artifacts. This distinction covers existing companion files such as `implementation-paths.json`; its reviewable changed-path content is already present in ledger-bound `delivery.json`.
6. Add bounded APIs:
   - `list(workflow_id, kinds, revisions)` returns metadata only;
   - `read_text(workflow_id, artifact_id)` rejects NUL/binary content and output over 1 MiB;
   - `export(workflow_id, artifact_id, output)` writes mode `0600`, refuses an existing destination unless an explicit overwrite flag is supplied, and verifies the exported digest before success.
7. Make `WorkflowService` construct and expose the catalog without importing dashboard or Hermes internals. Preserve current `status` JSON for compatibility; new artifact projections are additive and read-only.
8. Add the dashboard contract's strict `approval_summary` to the plan-submission tool schema, handler, service, immutable plan evidence, and bundled worker contract. Canonicalize it, bind it to the server-computed plan digest, retain its own SHA-256 digest, and record the plan reference plus summary in one ledger update after writing the immutable plan bytes. A failed ledger update may leave only an unreferenced file, never a partially authoritative packet. The plan worker may generate it; Daidala and the dashboard never invoke a model to recreate it. Invalid model output blocks plan completion.
9. Add an exact current-plan selection helper that returns one opaque artifact ID and its bound summary only when workflow, policy revision, plan revision, stage, artifact digest, and summary digest match the current ledger. Missing, binary, oversized, stale, or digest-mismatched plan content or a missing/invalid/unbound summary must block approval rather than fall back to a path or summary. Historical summary-less plans remain readable but require normal plan revision before approval.
10. Add `tests/test_artifact_access.py` covering every active reference kind, current and superseded plans, summary structure/bounds/source binding, legacy summary-less plans, missing/corrupt bytes, symlink/path escape, wrong workflow, stale/forged artifact IDs, text/binary bounds, export collision, mode `0600`, and no read-time ledger mutation.

**Verification gate:** `pytest tests/test_artifact_access.py tests/test_store.py tests/test_workflow.py tests/test_tools.py tests/test_worker_contract.py -q` exits 0; tests prove an arbitrary absolute path cannot reach the resolver and the current plan returns bytes plus a summary matching their exact bound ledger identities.

## Phase 1 — Add native and standalone CLI review/export commands

**Goal:** Let a local operator list, inspect, and export exact workflow evidence without manually traversing profile directories.

**Steps:**

1. Add a bounded verified member-read primitive to `daidala.archive_io`, then extend the Phase 0 resolver with archive availability states `archived` and `active-and-archived`. Resolve archived files only through an injected archive lookup keyed by exact `artifact_id`; reopen the tar, revalidate mode, manifest digest, member type, size, and content digest on every read/export, and use only P0100's `daidala.archive_io` mechanics. P0310 owns the persistent curator-state layout that implements the lookup.
2. Treat archived files lacking ledger references as supplemental restore bytes, never review evidence; preserve this distinction for companion files such as `implementation-paths.json`.
3. Extend the shared parser/dispatcher in `daidala/cli.py` so both entry points expose the same commands:
   - `hermes daidala artifacts list <workflow-id> [--json]`;
   - `hermes daidala artifacts show <workflow-id> <artifact-id>`;
   - `hermes daidala artifacts export <workflow-id> <artifact-id> --output <path> [--overwrite]`;
   - equivalent standalone `daidala artifacts ...` forms.
4. `list` prints artifact ID, kind/stage, policy and plan revisions, recorded digest, recorded time, size when known, and availability. It never prints artifact content or treats one revision as `latest`.
5. `show` writes only verified text within the 1 MiB document bound to stdout. Binary or oversized evidence exits nonzero and directs the operator to `export`; export remains finite at the shared archive per-file bound, and errors never include artifact bytes.
6. `export` accepts an operator-selected destination but never uses that path as a read source. It creates parent directories only when explicitly requested, refuses special-file/symlink destinations, writes through a same-directory temporary file, verifies the digest, and atomically replaces only with `--overwrite`.
7. Add archive-equivalence, parser, fake-service, output-bound, native/standalone parity, collision, and nonzero-error tests in `tests/test_cli.py`, `tests/test_artifact_access.py`, and `tests/test_archive_io.py`.
8. Exercise the installed help and commands in an isolated `HERMES_HOME`; document only syntax proven by that probe.

**Verification gate:** `pytest tests/test_cli.py tests/test_artifact_access.py tests/test_archive_io.py -q` exits 0, active/archive reads are digest-equivalent, and isolated native/standalone probes produce byte-identical `list --json` output with equivalent exit codes for show/export success and failure.

## Phase 2 — Add deterministic artifact curator, archive, pin, and restore

**Goal:** Move eligible old terminal-workflow artifact files into recoverable compressed archives using deterministic policy, with no LLM judgment and no automatic deletion.

**Steps:**

1. Add `daidala/artifact_curator.py` with a strict bounded profile-local state document at `<resolved-data-root>/daidala/artifact-curator.json`, mode `0600`. Store schema, policy, compare-and-swap digest, and canonical workflow rows containing `workflow_id`, `state`, `first_terminal_observed_at`, `last_transition_at`, `pinned`, and archive IDs. Cap rows and document bytes before parsing.
2. Reuse the Hermes Curator lifecycle shape with Daidala-specific eligibility:
   - `active → stale` after 30 days from `first_terminal_observed_at`;
   - `stale → archived` after 90 days from that timestamp;
   - defaults are configurable but curation is disabled by default;
   - pinned workflows bypass every automatic transition;
   - restore sets the workflow to `active` and pinned so the next pass cannot immediately rearchive it.
3. Define terminal eligibility without moving operational authority into the ledger:
   - delivered workflows require a current delivery artifact and `worktree_owned == false`;
   - cancelled/abandoned workflows require all referenced Kanban cards to be terminal/archived and no owned worktree;
   - unavailable or ambiguous Kanban state, pending approval, running/blocked cards, owned worktrees, missing ledger evidence, or concurrent ledger changes make the workflow ineligible;
   - the first safe observation starts the age clock; do not infer age from Git commit timestamps or filesystem mtimes.
4. Add a per-curator lock and per-workflow operation lock. Every apply re-reads the ledger, current Kanban state, curator compare-and-swap token, and artifact inventory immediately before mutation.
5. Store archives at `<resolved-data-root>/daidala/artifact-archives/<workflow-id>/<archive-id>.tar.gz` with an adjacent strict manifest. The manifest records schema, workflow ID, ledger update token, created time, original relative locations, sizes, and SHA-256 digests. It includes supplemental safe regular files for restore but labels them non-ledger evidence.
6. Use a crash-convergent order: create temporary archive and manifest; reopen and verify all members; atomically publish both; persist archive availability; then remove only source files listed in the verified manifest. If interrupted after publication, access may report `active-and-archived`; retry verifies equivalence and finishes cleanup. Never remove the policy-ledger SQLite row or workflow root.
7. Add service/CLI operations mirroring the useful Hermes Curator controls under the Daidala namespace: `status`, `run` (preview by default), `run --apply`, `pin`, `unpin`, `archive <workflow-id>` with explicit preview/apply, `list-archived`, and `restore <workflow-id> <archive-id>`. No operation invokes Hermes skill curation.
8. Restore through `archive_io.py` into operation-owned temporary files beneath the original workflow artifact root; verify every digest; refuse conflicting active bytes; publish with exclusive/atomic writes; update curator state only after all required ledger-bound files are available.
9. Never automatically prune archive files. Permanent deletion remains out of scope for this plan; archive storage can be bounded later through a separately approved, exact-name preview/apply design.
10. Add `tests/test_artifact_curator.py` covering policy bounds, terminal classification, unavailable Kanban, active/worktree exclusion, pin/unpin, age transitions, same-pass replay, concurrent ledger change, lock contention, archive failure before source removal, interruption after publication, active-and-archived recovery, corrupt archives, restore collision, sensitive-error redaction, and cross-profile isolation.

**Verification gate:** `pytest tests/test_artifact_curator.py tests/test_archive_io.py tests/test_store.py -q` exits 0; failure injection at every publication/removal boundary proves there is no state in which the only verified copy is lost.

## Phase 3 — Add authenticated dashboard review and curator controls

**Goal:** Let an authenticated dashboard user inspect exact artifact metadata and bounded text, download verified bytes, and manage reversible curator state without exposing arbitrary files.

**Steps:**

1. Extend `daidala/dashboard_backend.py` with projections over `artifact_access.py` and `artifact_curator.py`; keep path validation, digest verification, policy, and archive mutation out of the router.
2. Add authenticated plugin routes using workflow ID plus opaque artifact/archive IDs only:
   - metadata list;
   - bounded text view;
   - verified download with `Content-Disposition`, `Cache-Control: no-store`, and a non-sniffable content type;
   - curator status and preview;
   - confirmed pin/unpin/manual archive/restore using a fresh preview digest and literal `confirm: true`.
3. Reject path, filename, archive-member, and remote-URL parameters. Return classified 404/409/413 responses without absolute profile paths or sensitive content.
4. Extend `dashboard/dist/index.js` with an artifact panel that shows exact revision/digest/availability, renders text literally in a bounded escaped view, downloads binary/oversized evidence, distinguishes active from archived evidence, and never selects `latest` implicitly. Version 1 has no Markdown, JSON, YAML, source-code, HTML, or semantic diff renderer; it displays a diff as escaped unified-diff text and never executes or embeds artifact content.
5. Add a curator panel showing disabled/enabled policy, eligible/stale/archived counts, pinned workflows, next transition times, and preview-before-apply controls. Do not let browser polling update activity timestamps or keep artifacts artificially active.
6. Run browser verification in the existing isolated dashboard fixture pattern. Seed only synthetic non-secret artifacts; prove direct path traversal, unauthenticated requests, stale preview digests, and cross-profile IDs fail closed.

**Verification gate:** `pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py tests/test_artifact_access.py tests/test_artifact_curator.py -q` exits 0, and isolated Chromium verification lists an archived implementation diff, views its escaped text, downloads digest-equivalent bytes, restores it after confirmation, and cannot request an arbitrary filesystem path.

## Phase 4 — Add opt-in Hermes Cron scheduling

**Goal:** Run deterministic curation periodically through Hermes' existing profile-local Cron facility, without a Daidala daemon, nested `hermes chat`, or model judgment.

**Steps:**

1. Keep scheduling disabled by default. Enabling requires an operator preview and explicit confirmation that names the controller profile, interval, curator policy digest, and exact command/script identity.
2. Use only the supported public Hermes Cron surface. Before coding or documenting syntax, probe `hermes cron --help` and the supported Hermes version; do not import scheduler internals or write directly to the cron database.
3. Add an idempotent Daidala schedule preview/apply boundary that creates one profile-local script-only/no-agent Cron job invoking the installed Daidala curator apply path. The tick must inherit the controller profile's resolved data root, use no credentials, produce no artifact content, and emit output only for transitions or classified failures.
4. Persist the returned Cron job ID and schedule identity in curator state. Repeated setup converges on the same job; changed interval/policy requires a new preview digest. Disable/remove acts only on the recorded exact job ID and requires confirmation.
5. Each tick acquires the same curator lock and revalidates policy, ledger, Kanban, worktree, pin, and archive eligibility. A disabled policy exits successfully without mutation even if the Cron job still fires.
6. Add fake public-CLI tests plus an isolated-profile integration probe. Do not touch the current `hermes-vc` or `daidala-self-improvement` profiles during tests.

**Verification gate:** focused curator scheduling and CLI parity tests exit 0; in a disposable profile one tick archives one eligible fixture, a repeated tick makes no further change, disabled policy performs no mutation, and removal targets only the recorded Cron job ID.

## Phase 5 — Reconcile operator docs, DOX, package contents, and full verification

**Goal:** Make artifact review and curation discoverable from the supported operator path and prove the installed distribution preserves every security and profile boundary.

**Steps:**

1. Update `README.md` so the top-level feature summary and operator entry points include artifact review, export, archive availability, and recoverable curation without claiming unimplemented commit/push behavior.
2. Update `docs/02-workflow-state.md` with immutable ledger identity versus active/archive availability; update `docs/05-lifecycle-stages.md` with terminal artifact eligibility; update `docs/07-runbook.md` with exercised list/show/export/archive/restore commands; and update `docs/15-self-improvement.md` plus `docs/16-self-improvement-setup.md` with profile-local archive layout and recovery. Audit every numbered document and update any artifact-access, lifecycle, security, dashboard, or operator claim made stale by the implementation; do not leave the new behavior documented only in this plan.
3. Update dashboard documentation and the related dashboard plan so artifact review ownership, shared `archive_io.py`, and checkout-backup versus workflow-archive storage roots are unambiguous.
4. Perform the required DOX pass. Update `daidala/AGENTS.md`, `dashboard/AGENTS.md`, and `tests/AGENTS.md` for new modules, routes, CLI surfaces, archive responsibilities, and verification. Update root/docs indexes only if ownership or child structure changes; do not add diary entries.
5. Ensure `plugin.yaml`, package data, and release-content checks include only required code/assets. Do not package runtime archives, curator state, ledgers, fixture profiles, or generated review exports.
6. Exercise a fresh-wheel isolated profile: create a synthetic workflow, list exact artifact IDs, show text, export bytes, transition it through stale/archive using an injected clock, read directly from the archive, restore, and verify all SHA-256 values.
7. Run the complete repository verification and stop at the first unresolved failure:

   ```bash
   lefthook validate
   pytest
   ruff check .
   daidala packs validate addyosmani
   daidala packs validate aidlc
   python -m build
   python -m twine check dist/*
   python scripts/check_release_contents.py . --wheel dist/*.whl
   python scripts/check_md_links.py .
   ```

8. Review the final diff against this plan. Do not commit, push, install into a live controller profile, enable a live Cron job, or publish without separate explicit approval.

**Verification gate:** every command in step 7 exits 0; `README.md` and all affected numbered documents describe the exercised behavior rather than the plan; the fresh-wheel probe returns matching ledger, archive-manifest, viewed, exported, and restored digests; `git status --short` contains only reviewed source, tests, docs, and package metadata.

## Out of scope

- Automatic commit, push, pull-request creation, feature-branch integration, or any change to reviewed-diff-only delivery.
- Archiving workflows with an owned worktree, pending approval, or nonterminal Kanban cards.
- LLM-based artifact classification, summarization, deletion, or curator decisions.
- Permanent automatic or age-based deletion of artifact archives.
- Reading arbitrary filesystem paths, exposing profile roots to the browser, or sending artifact content through Kanban, Cron output, gateway messages, or model tools.
- Importing Hermes Curator or Cron private modules, modifying Hermes profile export format, or adding a Daidala daemon/server.
- Treating checkout backups as workflow artifacts or storing workflow archives under `<checkouts.root>`.
