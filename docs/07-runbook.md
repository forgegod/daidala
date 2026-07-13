# Daidala operator runbook

Daidala is operated through the native `hermes daidala` command. The
standalone `daidala` executable is the diagnostics-compatible form of the
same parser and handlers; it does not run a second agent or service.

## Install and enable

The supported host baseline is Hermes v0.18.2.

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
hermes daidala init --apply
```

The applied command creates the profile-local `daidala/workflows.sqlite3`
schema. Repeating it is safe. The dry run prints the target path and does not
create directories or files.

## Diagnose prerequisites

```bash
hermes daidala doctor
```

`doctor` validates the default Addyosmani pack against its pinned Git revision,
bounded Hermes version, exact installed skill names, and complete-directory
content digests. It is read-only and exits nonzero when the profile is not ready.
It requires network access to resolve the pinned source repository's current
HEAD.

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

## Approve the exact plan

Approval remains bound to the SHA-256 digest recorded on the current plan
artifact:

```bash
hermes daidala approve <workflow-id> <64-character-plan-digest>
```

Do not copy a digest from an older plan revision. A mismatch fails without
authorizing work. Generic `hermes kanban unblock` is not approval. Successful
approval completes the blocked gate and creates
`implement → verify → review → deliver` in one persistent worktree.

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

## Upgrade

```bash
hermes plugins update daidala
hermes daidala doctor
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
```

Use the native form operationally. The standalone executable exists for package
smoke tests and diagnostics, not as a separate orchestration runtime.
