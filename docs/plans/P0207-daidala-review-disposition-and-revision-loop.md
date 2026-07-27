# Daidala review disposition and revision loop

**Plan ID:** daidala-review-disposition-and-revision-loop

**Execution slot:** P0207

**Created:** 2026-07-25

**Depends on:** daidala-artifact-access-core

**Split from:** daidala-dashboard-setup-and-supervision

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0205 completed with exact active-artifact identity, verified bounded reads, and export

**Context sources:** [approval summary contract](daidala-dashboard-execution-contract.md#approval-summary-and-escaped-text-contract), [dashboard review contract](daidala-dashboard-execution-contract.md#review-disposition-and-revision-loop-contract), [dashboard current state](daidala-dashboard-execution-contract.md#current-state), [lifecycle blocking and recovery](../05-lifecycle-stages.md#blocking-and-recovery), P0205 completion evidence, plus `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** structured automated review evidence, an attended exact-evidence disposition gate before delivery, a revision-request loop that creates a new plan card and fresh approval without rewriting rejected history, and synchronized lifecycle/operator documentation

**Status:** complete — Phases 0–2 checkpointed on `feat/dashboard-constraint-revisions`

This plan makes automated review advisory evidence rather than delivery authority: an attended user must accept the exact reviewed tuple, request a new plan revision, or reject the workflow before delivery can exist.

## Current state

- Review workers submit strict canonical `ReviewRecord` evidence bound to the current plan, policy, constraints, implementation, passing verification, activation, structured summary digest, and review card. Accepted reviews cannot contain blocking findings.
- `ReviewDisposition` is separate attended authority over the exact review tuple. Kanban workers cannot invoke it, and stale review digests fail without mutation.
- Plan approval creates `implement → verify → review`; the delivery card is created idempotently only after `accept_delivery`, and delivery plus self-improvement completion fail closed without that exact accepted disposition.
- Legacy terminal ledgers remain readable. Active ledgers without structured review and disposition authority cannot deliver; no acceptance is inferred from historical free-form review prose.
- `review show` and preview-by-default `review decide` share one native/standalone parser and service path. Apply binds literal confirmation plus exact fresh review and preview digests; rationale input is direct bounded UTF-8 and its path is never persisted.
- `request_revision` persists canonical request and successor packets before host mutation, archives the recorded current post-gate card IDs, releases the owned worktree, moves verification/review/disposition into strict history, and creates one revision-addressed Plan card without new implementation authority.
- The revisioned Plan worker uses the normal activation/artifact boundary. Recording its plan resolves the request, and fresh exact plan approval alone creates the new worktree and revision-addressed `implement → verify → review` graph.
- Isolated current-host probes discovered native `hermes daidala review`, matched standalone help and error JSON/exit codes without state mutation, and validated both packs. The repository probe's default historical upstream pin `3ef6bbd2` now differs from Hermes' reported current upstream `0a2c245c`; the same probe passed when supplied the complete observed `0.19.0` / `2026.7.20` / `0a2c245c` tuple.

## Risk call-out

A stale or ambiguous review must never authorize delivery, and a revision request destroys the mutable worktree after preserving immutable evidence. Every attended action therefore uses a fresh preview digest over the exact plan, policy, constraints, implementation, verification, review, card, and worktree identities; apply re-reads those facts before mutation. Legacy active workflows with free-form reviews receive no inferred acceptance: they remain blocked for explicit migration, revision, or cancellation. Historical artifacts and card events remain immutable.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Enforce structured review and attended disposition | done (`python -m pytest -q tests/test_review_disposition.py tests/test_workflow.py tests/test_execution.py tests/test_tools.py`; full `python -m pytest -q`; `ruff check .`; `lefthook validate`; both pack validations; Markdown links; build, Twine, and release-content checks all exited 0) | `pytest -q tests/test_review_disposition.py tests/test_workflow.py tests/test_execution.py tests/test_tools.py` exits 0 and proves delivery cannot exist before an exact attended acceptance |
| 1 | Add review-driven plan revision loop and CLI | done (`pytest`; `ruff check .`; `lefthook validate`; both pack validations; isolated native/standalone review parity; Markdown links/tables; build, Twine, and release-content checks all exited 0) | `pytest -q tests/test_review_disposition.py tests/test_execution.py tests/test_kanban.py tests/test_cli.py tests/test_plugin.py` exits 0; an isolated supported-profile probe proves native/standalone help, JSON, exit-code parity, and fresh approval after revision |
| 2 | Reconcile lifecycle, operator, and worker documentation | done (focused and full tests, Ruff, Lefthook, both pack validations, Markdown links/tables, build, Twine, and release-content checks exited 0) | `pytest -q tests/test_worker_contract.py tests/test_cli.py tests/test_plugin.py && python scripts/check_md_links.py .` exits 0 and every current-behavior document distinguishes automated review, attended disposition, revision, and dashboard availability |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Enforce structured review and attended disposition

**Goal:** Replace free-form review authority with strict automated review evidence and one ledger-owned attended gate that alone may release delivery.

Steps:

1. Read the dashboard review contract, current state, P0205 evidence, and the complete `daidala/` and `tests/` AGENTS chains.
2. Add strict canonical review records binding workflow ID, plan/policy/constraint identity, implementation digest, sorted unique passing-verification digests, activation digest, outcome, the shared contract's structured approval summary, findings, and recorded time. The review worker may generate the summary from the exact diff, changed paths, verification, and findings; Daidala validates and binds it but performs no model call. The generated summary is decision support, never an implicit successor handoff: the canonical review view separately projects every durable identity/reference that a later disposition or revision can consume. Outcomes are exactly `accepted`, `changes_requested`, or `rejected`; accepted records cannot carry blocking findings.
3. Add bounded findings with stable IDs, severity, blocking flag, title, rationale, and ledger-bound evidence references. Reject unknown fields, duplicates, empty evidence, oversized text, stale identities, and review records created outside the current review card.
4. Replace free-form review submission with a review-specific worker operation. An accepted review completes the review card; `changes_requested` or `rejected` persists evidence, comments with the exact requested decision, and blocks the card as `needs_input`.
5. Add a strict human disposition record binding the exact review, implementation, verification, plan, policy, and constraint tuple plus action, actor, rationale, and decision time. Its read model distinguishes immutable metadata from operator rationale/feedback. Actions are exactly `accept_delivery`, `request_revision`, or `reject_workflow`.
6. Permit `accept_delivery` only for a current automated `accepted` review with no blocking findings and all required passing verification. Reject Kanban-worker authority exactly as plan approval does; a user who disputes reviewer judgment comments and unblocks the same review card instead of overriding a blocking review.
7. Stop creating `deliver` during plan approval. Create `implement → verify → review` only; after attended acceptance, record the disposition and create exactly one delivery card parented to the accepted review card. Make `deliver()` fail closed without that current disposition.
8. Handle legacy ledgers explicitly: terminal historical workflows remain readable, while active workflows lacking structured review identity cannot deliver and report migration/revision/cancellation as the available actions. Never synthesize acceptance from `review.md` prose.
9. Add positive, stale-tuple, worker-rejection, malformed-record, malformed or source-unbound summary, blocking-finding, legacy-ledger, idempotency, no-delivery-card-before-acceptance, and delivery-enforcement tests. Bind and persist the review summary digest to the implementation digest; make persisted review/disposition retries converge across Kanban failures; and migrate recommendation and self-improvement completion consumers from the removed free-form review artifact to the exact structured accepted-review/disposition tuple. Update state/store migrations and owning DOX in the same implementation change.

Verification gate: The Phase 0 command exits 0; an accepted automated review still cannot create or execute delivery until an attended actor accepts the exact current evidence tuple, and every stale or blocking state fails without mutation.

## Phase 1 — Add review-driven plan revision loop and CLI

**Goal:** Turn `request_revision` into a preserved, restart-safe loop that sends feedback to a new plan revision and repeats exact plan approval before any new implementation.

Steps:

1. Add a canonical revision-request artifact binding the source review/disposition preview, rejected implementation and verification identities, normalized human feedback, target plan revision, actor, and time. Store it before card or worktree mutation. Define its bounded **successor packet** read model before the dashboard implementation: source review/disposition/implementation/verification artifact IDs and digests; workflow, plan, policy, and nullable constraint revisions; target plan revision; pack and activation identities; and normalized feedback. It excludes raw logs, arbitrary filesystem paths, environment values, and full comment threads. The deterministic fields are read-only; feedback is the only operator-authored field.
2. Implement preview/apply service operations for `request_revision`. Preview reports cards to archive, worktree to release, preserved artifacts, next plan revision, and next assignee; apply requires the fresh preview digest and literal confirmation.
3. On apply, persist the revision request, invalidate plan and review approvals, archive current post-gate cards, and release the old worktree only after its immutable implementation, verification, and review evidence verifies. Replay converges without duplicate artifacts or cards.
4. Extend plan-card identity so initial planning uses revision 0 and revision requests create one new `plan` card for revision N. Parent it to the source review card when present, assign the existing plan profile, pin the pack's plan skills, and include only the successor packet's revision-request references/digests plus the durable goal, definition, and normalized feedback—not raw logs. The same canonical packet is returned by preview and apply and is the only metadata projection the dashboard presents as forwarded to the new card.
5. Make the revisioned plan worker produce `plan-N/plan.md` through the normal activation/evidence boundary. Recording it resolves the pending revision request, exposes a new exact plan-approval decision, and creates no worktree or implementation card before attended approval.
6. After fresh plan approval, create a fresh detached worktree from the recorded baseline and a new `implement → verify → review` graph for revision N. Preserve all prior plans, review decisions, verification outputs, dispositions, and card history.
7. Extend the shared parser/dispatcher with equivalent native `hermes daidala` and standalone `daidala` commands:
   - `review show WORKFLOW_ID` returns the current bounded review/disposition packet, exact tuple, allowed actions, card IDs, and (when a revision is possible or pending) the canonical successor packet without mutation or arbitrary paths;
   - `review decide WORKFLOW_ID ACTION --rationale-file PATH` previews one action and returns its exact review digest, preview digest, affected cards/worktree, and next state;
   - add `--apply --expected-review-digest SHA256 --expected-preview-digest SHA256` to apply that same decision after a fresh recomputation;
   - CLI actions are exactly `accept-delivery`, `request-revision`, and `reject-workflow`, mapping to the canonical underscore-valued service actions.
   The rationale/feedback file is UTF-8, bounded, direct, non-symlink input; its path is never persisted. Default execution is preview-only. A successful revision apply returns the new plan revision and plan card ID. Do not expose a general “move to phase” command.
8. Keep reviewer challenges on Hermes' native Kanban CLI rather than duplicating them: use `hermes kanban --board BOARD comment REVIEW_CARD_ID TEXT`, then `hermes kanban --board BOARD unblock REVIEW_CARD_ID --reason TEXT`. Document how `review show` supplies the board and review card ID.
9. Probe standalone and native help/JSON/exit-code parity in a fresh supported Hermes profile. If `hermes daidala` is not discovered, stop P0207 as a host/plugin prerequisite failure; do not publish native syntax based only on the standalone parser.
10. Treat reviewer disagreement without changed code as normal Hermes review-card comment/unblock. Treat changed code, verification scope, or implementation approach as `request_revision`. Goal or policy changes remain cancel/restart or constraint-replacement operations.
11. Add revision-card idempotency, stale preview, archive failure, worktree cleanup failure, replay, concurrent mutation, fresh approval, historical evidence, parser/help/JSON/exit-code parity, and no-direct-rewind tests.

Verification gate: The Phase 1 command exits 0; one confirmed request preserves rejected evidence, removes stale execution authority, creates exactly one revisioned plan card, and cannot create a new worktree or implementation card until the new plan digest is attendedly approved. In a fresh supported profile, native and standalone review commands expose equivalent help, JSON, mutations, and exit codes; failed native discovery blocks the phase.

Implementation evidence (2026-07-27): `PlanRevisionRequestReference` and strict historical review/disposition/verification collections preserve the source tuple and retry markers. `daidala/revision.py` owns bounded canonical review, decision-preview, revision-request, and successor packets; the successor packet carries opaque source review, disposition-preview, implementation, and verification IDs and digests without profile-local paths. `WorkflowService` persists intent before archive/worktree operations, resumes each durable checkpoint, advances to one revision-addressed Plan card, and withholds the worktree and post-gate graph until the successor plan is recorded and freshly approved. Shared CLI coverage proves action mapping, direct bounded rationale input, preview/apply identity gates, native/standalone dispatch parity, path exclusion, and absence of a direct rewind command. Cross-pack execution coverage injects artifact-write, recorded-ID archive, owned-worktree cleanup, and successor Plan-card failures; exact retries converge without duplicate host comments or cards, preserve immutable old evidence, record the successor plan through activation, and resume revision 1 only after approval.

Verification evidence (2026-07-27): full `python -m pytest -q`, `ruff check .`, `lefthook validate`, `daidala packs validate addyosmani`, `daidala packs validate aidlc`, `python scripts/check_md_links.py .`, Markdown table structure validation, `python -m build`, `python -m twine check dist/*`, and `python scripts/check_release_contents.py . --wheel dist/*.whl` exited 0. The release check observed 218 tracked files and 55 wheel members, including `daidala/revision.py`. A fresh isolated profile returned native and standalone review help plus byte-equivalent missing-workflow JSON/exit behavior with no state mutation; the plugin compatibility probe passed for the complete currently reported Hermes tuple `0.19.0` / `2026.7.20` / `0a2c245c`.

## Phase 2 — Reconcile lifecycle, operator, and worker documentation

**Goal:** Make every current-behavior document and bundled worker instruction describe the implemented review gate and revision loop without claiming the later dashboard presentation exists.

Steps:

1. Update `docs/README.md` support status, reading guidance, and symptom routing for review disposition and revision requests.
2. Update `docs/00-getting-started.md` with the complete practical journey: inspect automated review evidence, accept delivery, challenge reviewer judgment through comment/unblock, request a revision, review the new plan, and approve its new digest.
3. Update `docs/01-architecture.md`, `docs/02-workflow-state.md`, and `docs/05-lifecycle-stages.md` so diagrams, authority tables, transition ownership, card creation timing, immutable evidence, and revision identities show `review → human disposition → deliver` plus the revision loop.
4. Update `docs/06-security.md` and `docs/07-runbook.md` with attended authority, exact preview/apply tuples, stale-state rejection, legacy workflow handling, native/standalone commands, recovery, and the rule that blocking findings cannot be overridden.
5. Update `docs/10-autonomous-development-use-cases.md` and `docs/11-skill-usage-and-user-control.md` so rejected-implementation revision is no longer described as unsupported and review feedback/skill handoffs remain artifact-backed.
6. Audit `docs/08-hermes-integration.md`, `docs/09-pack-adapters.md`, `docs/14-workflow-constraints.md`, `docs/15-self-improvement.md`, `docs/16-self-improvement-setup.md`, and every active plan for stale review, delivery-card, approval, or revision claims; update only affected sections and preserve distinctions between generic workflow disposition and self-improvement retention/completion approval.
7. Update `daidala/skills/orchestrate/SKILL.md` and its worker-contract tests with the structured review operation, accepted-versus-blocked behavior, attended disposition boundary, request-revision handoff, and prohibition on direct phase rewind.
8. Perform the full DOX pass for root, `daidala/`, `dashboard/`, `docs/`, and `tests/`; update ownership, local contracts, route/tool inventories, and verification commands where the implementation changed them. Remove stale or contradictory text rather than adding migration diaries.
9. State the dashboard boundary explicitly: P0207 implements service and CLI authority; P0210 later renders those operations in the Hermes dashboard. Do not document unimplemented browser controls as current behavior.
10. Include copyable CLI journeys for accepted review, request revision, reject workflow, challenge reviewer, inspect the returned revisioned plan card, and perform the subsequent exact plan approval. Document standalone syntax only after its probe and native syntax only after native discovery/parity succeeds.

Verification gate: The Phase 2 command exits 0; searches find no current-behavior claim that delivery follows automated review without attended disposition, that rejected code must always cancel/restart, or that the dashboard controls exist before P0210.

Implementation evidence (2026-07-27): the root and documentation indexes, first-run walkthrough, architecture, policy-ledger ownership, pack reference/adapters, lifecycle, security, runbook, use cases, skill-control, market, triggering, and self-improvement documents now distinguish automated review evidence from exact attended disposition. Copyable native journeys cover review inspection, preview/apply acceptance, reviewer challenge through Kanban comment/unblock, revision request, returned Plan-card inspection, fresh plan approval, and workflow rejection. Current docs state that P0207 exposes service/CLI authority while P0210 owns later dashboard controls. The bundled `daidala:orchestrate` contract now forbids worker disposition and direct rewind, carries canonical successor feedback into revisioned planning, and requires fresh approval; worker-contract tests bind those rules. The active P0400 plan was reconciled to create delivery only after attended review acceptance. The DOX pass updated `docs/AGENTS.md`; root, `daidala/`, `dashboard/`, and `tests/` ownership/index contracts required no other changes because their current boundaries already matched the implementation.

Verification evidence (2026-07-27): `pytest -q tests/test_worker_contract.py tests/test_cli.py tests/test_plugin.py && python scripts/check_md_links.py .`, full `python -m pytest -q`, `ruff check .`, `lefthook validate`, both pack validations, Markdown table structure validation, `python -m build`, `python -m twine check dist/*`, `python scripts/check_release_contents.py . --wheel dist/*.whl`, and `git diff --check` exited 0. Targeted searches found no current-behavior claim that automated review creates delivery directly, rejected code must always cancel/restart, or P0207 already supplies dashboard controls.

## Out of scope

- Do not let a human override blocking findings or deterministic policy constraints; challenge reviewer judgment through comment/unblock or change policy through its existing revision gate.
- Do not mutate or reopen captured implementation files, completed card history, prior plans, reviews, verification evidence, or dispositions.
- Do not add arbitrary jumps to `define`, `verify`, or `implement`; changed implementation returns through a new plan revision, while changed goal starts a new workflow.
- Do not add commit, push, merge, pull-request, deployment, or release authority.
- Do not implement dashboard presentation in this plan; P0210 consumes these exact service operations.
