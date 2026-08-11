# Daidala operator runbook

Daidala is operated through the native `hermes daidala` command. The
standalone `daidala` executable is the diagnostics-compatible form of the
same parser and handlers; it does not run a second agent or service.

## Install and enable

Supported hosts are exact Hermes v0.18.2, v0.19.0, and v0.20.0 releases within
the bounded pack range `>=0.18.2,<0.21.0`.

```bash
hermes plugins install forgegod/daidala --enable
hermes plugins list
```

Run all commands under the Hermes profile that owns the workflow. Profile
selection is a Hermes concern; Daidala resolves the active profile through
Hermes' home path and never writes a global fallback.

## Initialize

Initialization is dry-run by default:

```bash
hermes daidala init
hermes daidala init --apply --preview-digest <preview-digest> --confirm
```

The applied command requires the fresh digest printed by the dry run and literal
confirmation. It creates the profile-local `daidala/policy-ledger.sqlite3`
schema. Repeating it with a fresh preview is safe and reports a no-op. The dry
run prints the target path and does not create directories or files.

## Diagnose prerequisites

```bash
hermes daidala doctor --project-manifest /absolute/repository/.daidala/project.yaml
```

`doctor` emits the strict self-improvement prerequisite report. Add
`--registration /profile/projects/<project-id>/registration.yaml` to bind the
trusted profile-local authority and `--live` to run bounded GitHub, gateway, and
container availability probes. Without `--live`, those checks are `not-run` and
the command exits `2`. Exit `0` means every documented check passed; exit `1`
means invalid input or checker failure. The command never fixes setup state.

Inspect and install pack dependencies explicitly:

```bash
hermes daidala packs list
hermes daidala packs validate addyosmani
hermes daidala packs install addyosmani
hermes daidala packs install addyosmani --apply
hermes daidala packs check addyosmani
```

Installation is also dry-run by default. Review every proposed `hermes skills
install` command before using `--apply`. Recursive installation is refused by
the verified Hermes baseline.

In the dashboard, Config → Packs lets you select any declared skill to inspect
its bounded literal `SKILL.md` text. Addyosmani skills that are not installed use
an attributed snapshot from the pack's pinned source revision; that display-only
preview does not satisfy the installed-skill or content-digest readiness gate.

## Start and resume a workflow

Start explicitly on an existing named board. One default profile is sufficient;
override only stages that need a different profile:

```bash
hermes daidala start /absolute/path/to/repo "Implement the requested change" \
  --board project-board \
  --default-profile engineer \
  --stage-profile define=architect \
  --stage-profile review=reviewer \
  --pack addyosmani \
  --workflow-id stable-workflow-id
```

Do not use `--profile`; Hermes consumes it as a host-level option before the
plugin command parser receives it. Daidala expands and validates the complete
stage map, then creates `define → plan`. Observe progress through normal Kanban
surfaces and use combined diagnostics when needed:

```bash
hermes kanban --board project-board watch
hermes daidala status stable-workflow-id
```

The gateway's Kanban dispatcher executes ready cards. The start command creates
the graph; it does not start a second scheduler, daemon, or nested agent.

## Start a Git-pinned plan phase

`start-from-plan` admits exactly one pending phase from a clean, full Git
revision. The plan path is repository-relative; Daidala reads its blob from the
named commit, not mutable checkout bytes. Preview first:

```bash
hermes daidala start-from-plan /absolute/path/to/repo \
  --plan-path docs/plans/P0440-example.md \
  --source-revision <full-commit-a> --phase 0 \
  --board project-board --default-profile engineer \
  --pack addyosmani --workflow-id example-phase-0
```

Apply only with the returned digest:

```bash
hermes daidala start-from-plan /absolute/path/to/repo \
  --plan-path docs/plans/P0440-example.md \
  --source-revision <full-commit-a> --phase 0 \
  --board project-board --default-profile engineer \
  --pack addyosmani --workflow-id example-phase-0 --apply \
  --expected-preview-digest <preview-digest>
```

The imported workflow has no synthetic `define` or `plan` card. Its dashboard
summary and approval recommendation show the Git-pinned source revision, Plan
ID, phase, packet digest, and `verified` packet state without source paths or
bytes. Approval binds that packet as well as the current plan and constraint
tuple.

Delivery remains uncommitted and unpushed. If an operator chooses to continue,
create one separately authorized direct child commit containing only the
delivered diff and the allowed `done (daidala:<workflow-id>:<delivery-digest>)`
phase-status projection. Then admit the next pending phase from the child commit
with a new workflow ID and `--predecessor-workflow-id <prior-workflow-id>`.
The prior approval cannot authorize that new packet or baseline.

## Review exact artifacts

List ledger-owned artifacts and select one exact opaque artifact ID. JSON list
output contains metadata only; it never includes artifact content or labels one
revision as `latest`:

```bash
hermes daidala artifacts list <workflow-id> --json
hermes daidala artifacts show <workflow-id> <artifact-id>
```

`show` writes only digest-verified UTF-8 text within the 1 MiB document bound.
For binary or larger artifacts, export verified bytes to a destination whose
parent directory already exists:

```bash
hermes daidala artifacts export <workflow-id> <artifact-id> \
  --output /operator/selected/artifact.bin
```

Export creates a mode-`0600` regular file atomically and refuses an existing
destination unless `--overwrite` is present. The destination is never accepted
as an artifact read source.

Preview and apply a manual terminal-workflow archive, then inspect or restore
one exact archive ID:

```bash
hermes daidala curator archive <workflow-id>
hermes daidala curator archive <workflow-id> --apply \
  --expected-preview-digest <archive-preview-digest>
hermes daidala curator list-archived
hermes daidala curator restore <workflow-id> <archive-id>
hermes daidala curator restore <workflow-id> <archive-id> --apply \
  --expected-preview-digest <restore-preview-digest>
```

Archive apply verifies every member before removing matching active sources.
Artifact list/show/export continue to resolve the unchanged ledger identities
from that archive. Restore writes only below the derived profile-local recovery
root, does not rewrite the ledger path, and leaves the verified archive intact.

## Schedule artifact curation

Policy and scheduling are disabled until an operator previews and confirms
their exact identities. Configure the curator policy, then register one
controller profile:

```bash
hermes daidala curator configure --enabled \
  --stale-after-days 30 --archive-after-days 90
hermes daidala curator configure --enabled \
  --stale-after-days 30 --archive-after-days 90 --apply \
  --expected-state-digest <state-digest> \
  --confirm-policy-digest <policy-digest>
hermes daidala curator schedule setup "every 1d"
hermes daidala curator schedule setup "every 1d" --apply \
  --expected-preview-digest <preview-digest> \
  --confirm-controller-profile <controller-profile>
```

The preview binds the interval, curator policy digest, and exact installed Bash
launcher. Setup creates or updates one profile-local script-only/no-agent Hermes
Cron job and records the returned job ID. Repeating unchanged setup reuses that
job. Policy or script changes require a new preview. Inspect and remove only the
recorded job with:

```bash
hermes daidala curator schedule status
hermes daidala curator schedule remove
hermes daidala curator schedule remove --apply \
  --expected-preview-digest <remove-preview-digest> \
  --confirm-controller-profile <controller-profile>
```

The gateway scheduler must be running. An idle or disabled-policy tick is
silent and performs no curator mutation; failures remain classified Cron runs.

## Approve the exact plan

Approval remains bound to the SHA-256 digest recorded on the current plan
artifact:

```bash
hermes daidala approve <workflow-id> <64-character-plan-digest>
```

Do not copy a digest from an older plan revision. A mismatch fails without
authorizing work. Generic `hermes kanban unblock` is not approval. Successful
approval records the ledger gate and creates
`implement → verify → review` in one persistent worktree. Automated review does
not create `deliver`.

## Review disposition

Inspect the bounded current packet before taking attended action:

```bash
hermes daidala review show <workflow-id>
```

The response supplies the board, review card ID, exact evidence tuple, current
disposition, allowed actions, and any pending successor packet. The dashboard
workflow detail exposes the same authority through a source-bound evidence panel:
preview the selected disposition, inspect its fixed consequences and successor
packet, check the literal confirmation, then apply. The browser never selects an
actor, card, artifact path, worktree path, or revision identity.

Every rationale file must be direct, regular, non-symlinked, non-empty UTF-8 and
at most 4096 bytes. The file path is input only and is never persisted.

For an accepted review with no blocking findings, preview and then apply exact
delivery acceptance:

```bash
printf '%s\n' 'Accepted after inspecting the exact review evidence.' > review-rationale.txt
hermes daidala review decide <workflow-id> accept-delivery \
  --rationale-file ./review-rationale.txt
hermes daidala review decide <workflow-id> accept-delivery \
  --rationale-file ./review-rationale.txt --apply \
  --expected-review-digest <review-digest> \
  --expected-preview-digest <preview-digest>
```

Preview is non-mutating. Apply re-reads the current tuple; stale review or
preview digests fail before mutation. Successful acceptance creates exactly one
`deliver` card. Blocking findings cannot be overridden.

If reviewer judgment is disputed but captured code need not change, use the
board and review-card ID from `review show`:

```bash
hermes kanban --board <board> comment <review-card-id> "Challenge: <reason>"
hermes kanban --board <board> unblock <review-card-id> --reason "Re-review requested"
```

If code, verification scope, or implementation approach must change, preview
and apply revision instead:

```bash
printf '%s\n' 'Address the findings and rerun the named verification.' > revision-feedback.txt
hermes daidala review decide <workflow-id> request-revision \
  --rationale-file ./revision-feedback.txt
hermes daidala review decide <workflow-id> request-revision \
  --rationale-file ./revision-feedback.txt --apply \
  --expected-review-digest <review-digest> \
  --expected-preview-digest <preview-digest>
```

Apply preserves the rejected plan, implementation, verification, review,
disposition, and card history; archives only recorded current post-gate cards;
releases only the owned worktree; and returns the new plan revision and Plan card
ID. Inspect the card, wait for `plan-N/plan.md`, inspect that plan, and apply its
new digest through the normal approval gate:

```bash
hermes kanban --board <board> show <plan-card-id> --json
hermes daidala status <workflow-id>
hermes daidala approve <workflow-id> <new-plan-digest>
```

No new worktree or implementation card exists before fresh approval. There is no
direct phase-rewind command.

To reject the workflow at the review gate, use the same preview/apply sequence
with `reject-workflow`:

```bash
printf '%s\n' 'Rejecting this workflow after inspecting its exact evidence.' > rejection-rationale.txt
hermes daidala review decide <workflow-id> reject-workflow \
  --rationale-file ./rejection-rationale.txt
hermes daidala review decide <workflow-id> reject-workflow \
  --rationale-file ./rejection-rationale.txt --apply \
  --expected-review-digest <review-digest> \
  --expected-preview-digest <preview-digest>
```

## Cancel

Cancellation requires an audit reason:

```bash
hermes daidala cancel <workflow-id> "Superseded by a different change"
```

Cancellation comments and archives the workflow's cards through public Hermes
operations and cleans only its Daidala-owned worktree. The policy and artifact
ledger remains available for diagnostics.

## Recovery

The optional `/daidala` view labels unavailable Kanban state instead of using a
cached status. Use **Refresh** after restoring the gateway or host CLI. Setup and
constraint previews are safe to repeat; confirmed starts are idempotent, while a
stale constraint digest must be previewed again before replacement.

Hermes Kanban owns retry and recovery:

1. Inspect the named board and card with `hermes kanban --board <slug> show <id>`.
2. Read the worker comment, run metadata, and exact block reason.
3. Correct missing profile skills or capability prerequisites without mutating
   another profile's store implicitly.
4. Comment with the decision or remediation, reassign when necessary, and use
   `hermes kanban --board <slug> unblock <id> --reason "..."`.
5. The dispatcher respawns the card with its full thread and preserved absolute
   worktree. Never fabricate replacement evidence.

Artifact-write, archive, worktree-release, and successor Plan-card failures in a
confirmed revision request are retryable with the same exact review and preview
digests. The persisted request and progress markers prevent duplicate authority;
do not cancel or manually rewind merely because one host mutation failed.

Legacy ledgers without structured review fields remain readable, but `review
show`, disposition, and delivery fail closed. Never infer acceptance from a
historical `review.md`. Resume the current review worker so it records supported
structured evidence when that graph remains active; otherwise cancel and start a
new workflow under the current contract.

## Dashboard equivalence

The optional **Daidala → Config → Runbook** panel links each runbook operation
to its bounded browser surface: initialization preview/apply and prerequisite
diagnosis, pack inspection, workflow supervision/resume, exact-plan approval,
review disposition, and cancellation. Browser workflow selection only reopens an
existing workflow for read-only polling; it never starts another graph or
scheduler.

Install, enable, upgrade, plugin removal, gateway lifecycle, and standalone
diagnostics remain native CLI operations. The dashboard renders their exact
commands as guidance only and has no plugin-management, restart, or generic
command-dispatch route.

## Upgrade

```bash
hermes plugins update daidala
hermes daidala doctor --project-manifest /absolute/repository/.daidala/project.yaml
hermes daidala packs check addyosmani
```

Do not widen the documented Hermes compatibility range based only on a successful
install. A new host version requires the repository's plugin-load, CLI, test,
build, and clean-install probes.

## Standalone diagnostics

The following forms are intentionally equivalent and return the same JSON and
exit code:

```bash
hermes daidala status <workflow-id>
daidala status <workflow-id>
hermes daidala review show <workflow-id>
daidala review show <workflow-id>
hermes daidala artifacts list <workflow-id> --json
daidala artifacts list <workflow-id> --json
hermes daidala artifacts show <workflow-id> <artifact-id>
daidala artifacts show <workflow-id> <artifact-id>
hermes daidala artifacts export <workflow-id> <artifact-id> --output <path>
daidala artifacts export <workflow-id> <artifact-id> --output <path>
```

Replacing the `hermes daidala` prefix with `daidala` in either `review decide`
preview/apply example above is also equivalent; both forms share one parser and
dispatch path.

Use the native form operationally. The standalone executable exists for package
smoke tests and diagnostics, not as a separate orchestration runtime.
