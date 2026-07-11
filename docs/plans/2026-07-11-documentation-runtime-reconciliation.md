# Documentation/runtime reconciliation plan

> Status: Approved — execution in progress.
>
> Baseline: `de49ffb0f7eb2b44c92f76bb0127dece7f4b9cf2`
> (`docs(trigger): explain [SILENT] marker semantics in cron prompts`).
>
> This plan authorizes no implementation by itself. Execute one phase at a time
> only after the user approves this plan. Phase 4 requires a separate structural
> decision before it may start.

## Goal

Reconcile Wingstaff's numbered documentation with the implemented activation,
approval, triggering, provenance, and verification contracts found during the
2026-07-11 audit. Keep the work documentation-only, preserve the current runtime
boundary, and remove completed implementation plans from normative
source-of-truth claims.

## Current context

- The working tree was clean on `main` when this plan was written.
- Runtime behavior and the main documentation set are broadly aligned.
- The audit found no runtime defect requiring source changes.
- Baseline verification passed with the repository test suite, Ruff, both pack
  validators, and the Markdown link checker.
- `docs/plans/2026-07-11-skill-relevance-activation-manifest.md` is marked done
  and retains phase history and test totals that are no longer durable contracts.
- `docs/AGENTS.md` requires stable implemented contracts to live in numbered
  architecture/operator documents rather than only in plans.

## Scope and constraints

- Edit documentation only. Do not modify `wingstaff/`, `tests/`, schemas, packs,
  or runtime behavior.
- Preserve the distinction between Wingstaff capabilities and Hermes-owned cron
  or webhook composition.
- Do not introduce current test totals or other time-sensitive counts into
  durable documentation.
- Keep source-of-truth lists ordered and concise.
- Do not archive, move, delete, or condense completed plans without the separate
  Phase 4 decision.
- Before every commit, run `git diff --stat` and reject unrelated working-tree
  drift.
- Commit messages must explain the operator or maintenance reason for the change,
  not narrate individual edited lines.

## Phase 0 — baseline and exact-claim survey

### Goal

Confirm that execution starts from the audited state and that no intervening
change invalidates the file and line references below.

### Files

Read-only survey of:

- `docs/02-workflow-state.md`
- `docs/05-lifecycle-stages.md`
- `docs/06-security.md`
- `docs/11-skill-usage-and-user-control.md`
- `docs/12-market-overview.md`
- `docs/README.md`
- `docs/plans/*.md`
- owning `AGENTS.md` files

### Steps

1. Run `git status --short --branch` and confirm the tree contains only this
   approved plan or is otherwise explicitly accounted for.
2. Re-read every target section and verify the cited runtime behavior against:
   `wingstaff/state.py`, `wingstaff/workflow.py`, `wingstaff/service.py`,
   `wingstaff/tools.py`, and the relevant tests.
3. Search for sibling copies of each stale phrase or contract so a correction
   does not leave the documentation internally inconsistent.
4. Record any newly discovered runtime mismatch as a separate finding. Do not
   silently expand this documentation plan into a code change.

### Gate

```bash
python scripts/check_md_links.py .
pytest
ruff check wingstaff tests scripts
wingstaff packs validate addyosmani
wingstaff packs validate aidlc
```

### Stop condition

Stop if the baseline is dirty beyond the approved plan, any gate fails, or the
runtime no longer matches the audit. Resolve or re-plan before Phase 1.

No commit is created for this read-only phase.

## Phase 1 — correct stale normative and provenance claims

### Goal

Remove factual drift without changing the documented product boundary.

### Files and changes

#### `docs/02-workflow-state.md`

Replace the source-of-truth entry that names "the active Kanban-native
implementation plan". State that this numbered document owns the contract and
that `wingstaff/state.py`, `wingstaff/workflow.py`, `wingstaff/store.py`, and the
relevant service/Kanban modules implement it.

#### `docs/05-lifecycle-stages.md`

Remove "the active Kanban-native implementation plan" from the source-of-truth
list. Keep this numbered document as the lifecycle contract and retain direct
runtime and test references.

#### `docs/06-security.md`

Replace the ambiguous opening claim that cron is unavailable with wording that
preserves both boundaries:

> Wingstaff provides no scheduler and no commit or push surface. Hermes cron and
> webhooks may admit work through the composition documented in
> [Autonomous triggering](../13-autonomous-triggering.md), which is not yet verified
> end to end and does not weaken Wingstaff's approval gate.

Keep commit/push unavailable as a Wingstaff runtime capability. Do not imply that
Wingstaff owns Hermes scheduling or webhook infrastructure.

#### `docs/12-market-overview.md`

Use `https://github.com/mattpocock/skills` as the reader-facing source and retain
commit `391a2701dd948f94f56a39f7533f8eea9a859c87` as the assessed revision. Keep
the local `forgegod/mattpocock-skills` checkout only as assessment provenance and
retain the warning that a production pack must choose one authoritative source.
Replace the evidence-table citation to `../mattpocock-skills/` with the upstream
URL plus the assessed revision.

### Verification

```bash
python scripts/check_md_links.py .
git diff --check
git diff --stat
```

Re-read all changed sections and search the repository for:

- `active Kanban-native implementation plan`
- `Cron and target commit/push remain unavailable`
- `../mattpocock-skills`

Every remaining hit must be intentional and explained before committing.

### Proposed commit

```text
docs(runtime): remove stale plan and capability claims
```

The commit rationale should lead with preventing completed plans and
machine-local evidence paths from being mistaken for current runtime contracts.

### Stop condition

Stop if the security wording overstates trigger verification, if the upstream
Matt Pocock source cannot support the retained claims, or if an inbound reference
requires a different source-of-truth structure.

## Phase 2 — make activation and revision gates explicit

### Goal

Expose existing fail-closed behavior at the primary lifecycle and activation
entry points so operators do not have to infer it from lower-level prose.

### Files and changes

#### `docs/05-lifecycle-stages.md`

Immediately before the stage-contract table, add this contract:

> Every executable stage requires a current, finalized, unblocked skill
> activation manifest before Wingstaff records its durable handoff. Approval is
> the only non-executable card and has no activation manifest.

Update the Approval row to use:

- Input: `Current plan revision and digest`
- Durable handoff: `Approval actor, time, revision, and digest`

Keep the existing human-gate section, but make the invalidation rule explicit:
replacing a plan increments the revision, clears approval, and requires a new
matching approval before post-gate work can proceed.

Do not add a large table column if the preamble communicates the invariant more
clearly. If a table row is edited, inspect the rendered Markdown shape and verify
that no row begins with a doubled `||`.

#### `docs/11-skill-usage-and-user-control.md`

After the persisted-manifest validation paragraph, add a concise authorization
paragraph stating that:

- `wingstaff_record_skill_activation` reads `HERMES_KANBAN_BOARD` and
  `HERMES_KANBAN_TASK` from the dispatcher-owned worker environment;
- both values must match the workflow ledger's board and current stage card;
- calls outside the matching Kanban worker fail closed;
- model-supplied workflow or stage fields do not grant card authority;
- the handler's generic `task_id` context is turn isolation, not Kanban identity.

### Verification

```bash
python scripts/check_md_links.py .
git diff --check
git diff --stat
pytest tests/test_tools.py tests/test_workflow.py tests/test_execution.py
```

Cross-check the final wording against:

- `wingstaff/tools.py::record_skill_activation`
- `wingstaff/service.py::WorkflowService.record_skill_activation`
- `wingstaff/state.py::WorkflowLedger.activation_for`
- `wingstaff/workflow.py::_require_stage_activation`
- `wingstaff/workflow.py::replace_plan`

### Proposed commit

```text
docs(lifecycle): expose activation and revision authorization
```

The commit rationale should explain that operators need the fail-closed
prerequisites at the lifecycle entry point, not only in implementation details.

### Stop condition

Stop if the wording implies that Wingstaff can prove methodology was applied
before activation, or if it treats generic Kanban unblock as approval.

## Phase 3 — align support and verification references

### Goal

Make high-level support claims point to the tests that actually enforce the new
activation boundary.

### Files and changes

#### `docs/06-security.md`

Expand the source-of-truth test references by responsibility:

- pack and registration boundary: `tests/test_packs.py`, `tests/test_plugin.py`;
- handler/card authorization and activation policy: `tests/test_tools.py`,
  `tests/test_workflow.py`;
- persistence, artifact recovery, and executable path: `tests/test_store.py`,
  `tests/test_execution.py`.

Preserve the existing source-of-truth section order.

#### `docs/README.md`

Expand the Lifecycle stages support-status row so its implemented status names:

- approval graph;
- host-bound activation authorization;
- pending/finalized recovery;
- fail-closed evidence gates;
- worker handoff and recovery.

Keep the row compact; detailed behavior remains owned by
`docs/05-lifecycle-stages.md` and `docs/11-skill-usage-and-user-control.md`.

### Verification

```bash
python scripts/check_md_links.py .
git diff --check
git diff --stat
pytest
ruff check wingstaff tests scripts
wingstaff packs validate addyosmani
wingstaff packs validate aidlc
```

### Proposed commit

```text
docs(status): align activation support with enforcement tests
```

The commit rationale should explain that support claims need direct evidence for
host identity, recovery, and persistence—not merely a generic "activation gate"
label.

### Stop condition

Stop if the README row becomes a second detailed contract or if any cited test
module does not cover the stated responsibility.

## Phase 4 — completed-plan disposition

### Goal

Decide whether completed implementation plans should remain in place, move to an
archive, or become concise completed-design records after their stable contracts
have been verified in numbered documentation.

### Separate approval required

Before this phase, the user must choose one option:

1. Leave completed plans unchanged as historical records.
2. Move completed plans to `docs/plans/archive/` and update every inbound link and
   `AGENTS.md` index affected by the structural change.
3. Replace each completed plan with a concise design record that retains durable
   decisions, links to the numbered source-of-truth documents, and drops phase
   diaries, checkpoint commands, and historical test totals.

The initial candidate is:

- `docs/plans/2026-07-11-skill-relevance-activation-manifest.md`

The same decision should explicitly include or exclude:

- `docs/plans/2026-07-11-kanban-native-wingstaff-integration.md`
- `docs/plans/2026-07-10-wingstaff-bootstrap-and-roadmap.md`

Do not assume all three plans have the same disposition. Audit each one for
unique durable contracts before moving, deleting, or condensing it.

### Required survey before any structural edit

1. Classify every section as durable contract, duplicated current documentation,
   or historical execution record.
2. Map every durable contract to a numbered document and current runtime source.
3. Search all inbound links, bare path mentions, and `AGENTS.md` ownership/index
   entries.
4. Present the classification and proposed file operation for user confirmation.
5. Only then perform the separately approved structural edit.

### Verification if approved

```bash
python scripts/check_md_links.py .
git diff --check
git diff --stat
pytest
ruff check wingstaff tests scripts
```

Re-run repository searches for old plan paths and historical test-count phrases.
No dead links, stale source-of-truth claims, or duplicated normative contracts
may remain.

### Proposed commit

Choose only after the user selects the disposition. Examples:

```text
docs(plans): archive completed activation implementation record
```

or:

```text
docs(plans): replace activation phase diary with durable record
```

### Stop condition

Do not execute this phase without explicit approval of the option and exact file
set. Stop if any plan contains a durable contract not yet represented in the
numbered documentation.

## Final reconciliation gate

After all approved phases:

```bash
lefthook validate
python scripts/check_md_links.py .
pytest
ruff check .
wingstaff packs validate addyosmani
wingstaff packs validate aidlc
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
git status --short --branch
git diff --stat
```

Confirm:

- no runtime source changed;
- changed paths match only approved documentation phases;
- all corrected phrases were re-surveyed across sibling sections;
- every completed commit has the repository-local author identity;
- no commit or push occurred unless separately requested.

## Expected files likely to change

Phases 1–3:

- `docs/02-workflow-state.md`
- `docs/05-lifecycle-stages.md`
- `docs/06-security.md`
- `docs/11-skill-usage-and-user-control.md`
- `docs/12-market-overview.md`
- `docs/README.md`

Phase 4 only if separately approved:

- selected files under `docs/plans/`
- `docs/AGENTS.md` if plan structure or ownership changes
- any documentation containing inbound references to moved or replaced plans

## Risks and tradeoffs

- Clarifying Hermes cron composition can accidentally imply Wingstaff owns a
  scheduler. The security text must retain the unverified, host-owned boundary.
- Lifecycle table edits can create malformed Markdown or duplicate detailed
  contracts. Prefer one preamble invariant over another wide column.
- Host-owned activation identity is an implementation-specific operational
  contract tied to the verified Hermes boundary; keep its wording grounded in
  the current runtime and integration documentation.
- Replacing local market evidence with an upstream URL improves portability but
  must retain the assessed revision and origin discrepancy as provenance.
- Archiving plans reduces normative drift but can erase rationale or break links
  if performed before a claim-by-claim absorption audit.
- Broad source-of-truth lists can themselves drift. Keep them short and organized
  by responsibility rather than enumerating every test.

## Open decisions

1. Approve Phases 0–3 as written, or adjust their grouping and proposed commit
   boundaries.
2. For Phase 4, choose leave unchanged, archive, or replace with concise design
   records.
3. If Phase 4 is approved, specify whether it applies only to the activation plan
   or also to the completed Kanban-native and bootstrap plans.
4. Decide whether Phase 4 should be a separate task after Phases 1–3 land; this is
   recommended because it is structural and has a different rollback profile.
