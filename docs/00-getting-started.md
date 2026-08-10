# Getting started with Daidala

This walkthrough starts one Daidala workflow from the native Hermes CLI and
follows it through exact plan approval, automated review, attended disposition,
an optional plan revision with fresh approval, and delivery. Daidala creates the
graph; the Hermes gateway's Kanban dispatcher executes ready cards.

For guided onboarding, load `daidala:setup`. It checks the same prerequisites,
previews the exact `daidala_start` request, and requires explicit confirmation
before mutation. The skill works without the web dashboard; `/daidala` is an
optional visual path when the dashboard extension is installed.

In `/daidala`, enter the existing board, absolute repository path, and goal,
then select **Preview mutations**. Review the exact request before checking the
confirmation box; **Start workflow** remains disabled until confirmation.
Repeating the confirmed request reuses the same workflow and Kanban graph.

## 1. Check the prerequisites

Use exact Hermes Agent v0.18.2, v0.19.0, or v0.20.0 within
`>=0.18.2,<0.21.0`. The target
must be a clean local Git repository. Run these commands in the Hermes profile
that will own the workflow:

```bash
hermes plugins install forgegod/daidala --enable
hermes plugins list
hermes daidala packs check aidlc
```

For a registered self-improvement project, the read-only checklist diagnostic is
`hermes daidala doctor --project-manifest PATH [--registration PATH] [--live]`;
see [Self-improvement environment prerequisites](16-self-improvement-setup.md).
For the Addyosmani pack, preview and then explicitly apply its pinned
external-skill installation plan:

```bash
hermes daidala packs install addyosmani
hermes daidala packs install addyosmani --apply
hermes daidala packs check addyosmani
```

Every assigned profile must have the plugin and the card's exact skills
available. The minimal path below uses one profile for all stages. Dedicated
architect, implementation, verification, or review profiles are optional.

## 2. Create a board and run the gateway

```bash
hermes kanban boards create project-board --name "Project board" --switch
hermes gateway run
```

Run `hermes gateway run` in a separate terminal on WSL, Docker, or another
foreground-oriented environment. On a host with an installed gateway service,
`hermes gateway start` is the background-service form. The gateway contains the
Kanban dispatcher that claims ready cards; Daidala has no dispatcher loop of
its own.

## 3. Start explicitly

```bash
hermes daidala start /absolute/path/to/repo "Implement the requested change" \
  --board project-board \
  --default-profile default \
  --pack aidlc \
  --workflow-id first-workflow
```

Inputs:

- `target_repository`: absolute path to the clean Git checkout;
- `goal`: the complete development goal;
- `--board`: an existing named Kanban board;
- `--default-profile`: an existing profile assigned to every executable stage;
- `--pack`: `aidlc` for the bundled first-run path or `addyosmani` after its
  external skills pass `packs check`;
- `--workflow-id`: a stable identifier reused for restart-safe invocation.
- optional `--constraints-file PATH` or `--constraints-skill NAME` with
  `--constraints-skill-digest SHA256`: the initial workflow policy source.

Use `hermes daidala replace-constraints WORKFLOW_ID EXPECTED_DIGEST` with the
same file/skill selectors to create a new policy revision. Pass no positional
digest only when the workflow currently has no constraints.

Do not use `--profile`; Hermes consumes that host-level option before the plugin
subcommand parser receives it. Override individual stages only when needed:

```bash
--stage-profile define=architect --stage-profile review=reviewer
```

Observable result: Daidala records the clean baseline and creates linked
`define → plan` cards with deterministic idempotency keys. Repeating the same
start command returns the same workflow and cards.

## 4. Observe definition and planning

Use normal Hermes surfaces:

```bash
hermes kanban --board project-board watch
hermes kanban --board project-board list --json
hermes daidala status first-workflow
```

The worker first calls `kanban_show`, uses the skills pinned to its card, records
its artifact through a Daidala evidence tool, and completes with structured
`daidala.handoff/v1` metadata. The `plan` card becomes runnable after `define`
completes.

### What a Daidala card contains

A card is both a normal Hermes Kanban task and the practical input envelope for
one Daidala stage. Daidala sets its title, body, assignee, parent links, pinned
skills, workspace, and deterministic idempotency key. Hermes then owns status,
claims, comments, attempts, retries, and completion runs.

A representative initial card looks like this:

```text
title: daidala first-workflow: define
assignee: default
parents: []
workspace: dir:/absolute/path/to/repo
skills:
  - daidala:orchestrate
  - <exact pack-stage candidate skills>

body:
  Daidala workflow: first-workflow
  Stage: define
  Plan revision: 0
  Policy revision: 0
  Pack: aidlc
  Pack revision: <pinned source revision>
  Goal: Implement the requested change
  --- Workflow constraints ---
  Constraint revision: none
  Constraint digest: none
  Constraint artifact: none
  Block if a constraint conflicts with requested work or prescribes methodology/capabilities.
  --- End workflow constraints ---
  Use Daidala policy/evidence tools; Hermes Kanban owns lifecycle state.
```

The body is not the worker's entire context. `kanban_show` also exposes completed
parent handoffs, comments, and prior attempts. This lets a later stage recover
the durable output of its parent without copying large artifacts into the next
card. Artifact bodies and raw logs stay in Daidala-owned files; cards and runs
carry their paths, digests, and concise summaries.

On success, the worker does not rewrite the opening body. It completes the
Hermes run with a summary and structured metadata. The common handoff shape is:

```json
{
  "schema": "daidala.handoff/v1",
  "workflow_id": "first-workflow",
  "stage": "define",
  "plan_revision": 0,
  "policy_revision": 0,
  "constraints_revision": null,
  "constraints_digest": null,
  "pack": "aidlc",
  "pack_revision": "<pinned source revision>",
  "outcome": "completed",
  "artifact_refs": ["<definition artifact digest>"],
  "skill_activation_digest": "<activation manifest digest>",
  "active_skills": ["<applicable skill name>"]
}
```

This creates two complementary records: Hermes Kanban preserves the operational
thread and handoff history, while the Daidala policy ledger remains authoritative
for approval tuples, revisions, activation manifests, artifact integrity, and
worktree ownership. Approval is therefore not metadata on a runnable card and
has no card of its own. See [Lifecycle stages and handoffs](05-lifecycle-stages.md)
for the stage-specific fields added after implementation begins.

The Kanban board does not render the plan artifact body at the approval gate.
Use the authenticated dashboard artifact browser or the CLI to select the exact
ledger-owned plan artifact ID and read its digest-verified literal text:

```bash
hermes daidala artifacts list first-workflow --json
hermes daidala artifacts show first-workflow <plan-artifact-id>
```

Compare the selected artifact's recorded digest with the pending approval digest
before approving. If Daidala cannot verify and display the plan artifact, the
workflow is not reviewable and must remain unapproved.

After planning, Daidala exposes the exact pending approval tuple from its ledger.
It creates no approval card, implementation worktree, or implementation-capable
card.

## 5. Approve the exact plan

Run `hermes daidala artifacts list first-workflow --json`, select the exact plan
artifact ID, and review it with `hermes daidala artifacts show`, or inspect the
same verified literal artifact in the authenticated dashboard. Do not approve
from a pending-decision label or digest alone. Approve only after the plan,
risks, scope, and verification criteria are visible and acceptable, and the
displayed 64-character SHA-256 digest matches:

```bash
hermes daidala approve first-workflow <64-character-plan-digest>
```

A stale or changed digest fails closed. `hermes kanban unblock` cannot satisfy
Daidala approval policy, and a Kanban worker cannot call the approval tool.
Successful attended approval records the exact tuple in the ledger, creates one
detached worktree, and creates these cards with `plan` as their graph parent:

```text
implement → verify → review
```

The delivery card does not exist yet. Automated review produces bounded evidence;
it never authorizes delivery.

## 6. Review and attended disposition

All post-gate cards share the Daidala-owned worktree. Hermes Kanban owns their
status, assignment, dependencies, retry history, comments, and runs. Daidala
owns the captured implementation scope and evidence:

- `implement`: immutable diff and changed-path manifest;
- `verify`: exact commands, exit codes, and content-addressed outputs;
- `review`: structured outcome, summary, bounded findings, and exact evidence
  digests against the captured diff and passing verification.

Inspect a card or combined workflow status with:

```bash
hermes kanban --board project-board show <card-id> --json
hermes daidala status first-workflow
hermes daidala review show first-workflow
```

`review show` returns the current board, review card ID, exact evidence tuple,
allowed attended actions, and any pending successor packet. Blocking findings
cannot be overridden. If the review judgment is wrong and the captured code does
not need to change, comment on and unblock the same review card:

```bash
hermes kanban --board project-board comment <review-card-id> "Challenge: <reason>"
hermes kanban --board project-board unblock <review-card-id> --reason "Re-review requested"
```

After an accepted review with no blocking findings, write a non-empty UTF-8
rationale of at most 4096 bytes to a direct regular, non-symlink file and preview
exact acceptance:

```bash
printf '%s\n' 'Reviewed the exact evidence tuple; delivery is accepted.' > review-rationale.txt
hermes daidala review decide first-workflow accept-delivery \
  --rationale-file ./review-rationale.txt
```

Copy `preview.review_digest` and `preview.preview_digest` from that non-mutating JSON,
then apply the unchanged decision:

```bash
hermes daidala review decide first-workflow accept-delivery \
  --rationale-file ./review-rationale.txt --apply \
  --expected-review-digest <review-digest> \
  --expected-preview-digest <preview-digest>
```

Only this attended acceptance creates `deliver`. Delivery records reviewed
references with `committed: false` and `pushed: false`; it does not commit or
push the target repository.

If captured code, verification scope, or the implementation approach must
change, preview and apply `request-revision` with the same exact-digest pattern:

```bash
printf '%s\n' 'Address the blocking findings and rerun the named verification.' > revision-feedback.txt
hermes daidala review decide first-workflow request-revision \
  --rationale-file ./revision-feedback.txt
hermes daidala review decide first-workflow request-revision \
  --rationale-file ./revision-feedback.txt --apply \
  --expected-review-digest <review-digest> \
  --expected-preview-digest <preview-digest>
```

Apply preserves the old implementation, verification, review, disposition, and
card history before archiving the recorded post-gate cards and releasing only
the owned worktree. It returns the new plan revision and revision-addressed Plan
card ID. Inspect that card with `hermes kanban --board project-board show
<plan-card-id> --json`. After its worker records `plan-N/plan.md`, inspect the new
plan and approve its new digest with `hermes daidala approve first-workflow
<new-plan-digest>`. No new worktree or implementation card exists before that
fresh approval. There is no direct phase-rewind command.

To reject the entire workflow instead, preview and apply `reject-workflow` using
the same rationale and exact digest arguments. The generic `hermes daidala
cancel` remains the explicit cancellation path outside a current review gate.

These service and CLI operations are current. The optional authenticated
dashboard renders the same source-bound review evidence and preview-confirm
accept-delivery, request-revision, and reject-workflow controls.

## 7. Start a Git-pinned phase

Use `start-from-plan` when a repository-tracked plan already names one pending
phase. The plan path is repository-relative and the source revision is the full,
clean Git commit that becomes the implementation baseline. Dry run first:

```bash
hermes daidala start-from-plan /absolute/path/to/repo \
  --plan-path docs/plans/P0440-example.md \
  --source-revision <commit-a> --phase 0 \
  --board project-board --default-profile default \
  --pack aidlc --workflow-id example-phase-0
```

The response names only bounded source metadata and a `preview_digest`. Apply
the unchanged request with that digest:

```bash
hermes daidala start-from-plan /absolute/path/to/repo \
  --plan-path docs/plans/P0440-example.md \
  --source-revision <commit-a> --phase 0 \
  --board project-board --default-profile default \
  --pack aidlc --workflow-id example-phase-0 --apply \
  --expected-preview-digest <preview-digest>
```

Imported-plan workers treat the captured packet and copied plan artifact as
immutable. The source plan remains `pending` while Daidala runs it; neither
workers nor delivery edit it, commit it, or push it. After accepted delivery,
an operator separately creates one authorized Git child commit containing only
the delivered diff and the exact `done (daidala:<workflow-id>:<delivery-digest>)`
status projection. Start phase 1 from that new commit with its own workflow ID
and `--predecessor-workflow-id example-phase-0`; its packet and approval are new.

## 8. Recover or cancel

For a blocked worker, read its comment and run history, correct the prerequisite,
comment with the human decision, and unblock the same card:

```bash
hermes kanban --board project-board comment <card-id> "Remediation completed"
hermes kanban --board project-board unblock <card-id> --reason "Retry approved"
```

The dispatcher respawns the card with its thread and persistent workspace.
Verification and review must not mutate an already captured implementation; code
changes use the attended `request-revision` flow above. A comment/unblock is only
for re-review without changing captured code; it grants neither review
disposition nor plan approval.

Cancel Daidala-owned resources explicitly:

```bash
hermes daidala cancel first-workflow "Superseded by another change"
```

This comments and archives the workflow cards and removes only the Daidala-owned
worktree. The policy and artifact ledger remains available for diagnostics.

## Trigger and runtime boundary

Daidala does not schedule workflow admission. A workflow starts through an
explicit `hermes daidala start` command or an agent call to `daidala_start`;
external Cron may optionally initiate that same action. Artifact curation is the
narrow exception: `hermes daidala curator schedule setup` can explicitly create
one profile-local script-only/no-agent Hermes Cron job after preview and literal
controller-profile confirmation. Daidala still adds no scheduler or daemon and
does not replace the gateway dispatcher.

Hermes issue
[#34977](https://github.com/NousResearch/hermes-agent/issues/34977) concerns the
global orchestrator profile used by host goal decomposition. Daidala does not
use that routing path: it selects a board, expands a complete explicit
stage-to-profile map, and creates each card directly. Native and standalone CLI
processes use documented `hermes kanban` subprocess operations; agent-facing
tools use the in-process plugin tool registry. Both produce the same graph.

## Next references

- [Operator runbook](07-runbook.md)
- [Architecture and authority split](01-architecture.md)
- [Lifecycle stages and handoffs](05-lifecycle-stages.md)
- [Hermes compatibility boundary](08-hermes-integration.md)
- [Install the dashboard into one specific profile](08-hermes-integration.md#per-profile-installation) — symlink or public-Git install per Hermes profile, plus the dashboard-tab verification recipe
