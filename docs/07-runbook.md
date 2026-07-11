# Wingstaff operator runbook

Wingstaff is operated through the native `hermes wingstaff` command. The
standalone `wingstaff` executable is the diagnostics-compatible form of the
same parser and handlers; it does not run a second agent or service.

## Install and enable

The supported host baseline is Hermes v0.18.2.

```bash
hermes plugins install forgegod/hermes-wingstaff --enable
hermes plugins list
```

Run all commands under the Hermes profile that owns the workflow. Profile
selection is a Hermes concern; Wingstaff resolves the active profile through
Hermes' home path and never writes a global fallback.

## Initialize

Initialization is dry-run by default:

```bash
hermes wingstaff init
hermes wingstaff init --apply
```

The applied command creates the profile-local `wingstaff/workflows.sqlite3`
schema. Repeating it is safe. The dry run prints the target path and does not
create directories or files.

## Diagnose prerequisites

```bash
hermes wingstaff doctor
```

`doctor` validates the default Addyosmani pack against its pinned Git revision,
bounded Hermes version, exact installed skill names, and complete-directory
content digests. It is read-only and exits nonzero when the profile is not ready.
It requires network access to resolve the pinned source repository's current
HEAD.

Inspect and install pack dependencies explicitly:

```bash
hermes wingstaff packs list
hermes wingstaff packs validate addyosmani
hermes wingstaff packs install addyosmani
hermes wingstaff packs install addyosmani --apply
hermes wingstaff packs check addyosmani
```

Installation is also dry-run by default. Review every proposed `hermes skills
install` command before using `--apply`. Recursive installation is refused by
the verified Hermes baseline.

## Start and resume a workflow

Start explicitly on an existing named board. One default profile is sufficient;
override only stages that need a different profile:

```bash
hermes wingstaff start /absolute/path/to/repo "Implement the requested change" \
  --board project-board \
  --default-profile engineer \
  --stage-profile define=architect \
  --stage-profile review=reviewer \
  --pack addyosmani \
  --workflow-id stable-workflow-id
```

Do not use `--profile`; Hermes consumes it as a host-level option before the
plugin command parser receives it. Wingstaff expands and validates the complete
stage map, then creates `define → plan`. Observe progress through normal Kanban
surfaces and use combined diagnostics when needed:

```bash
hermes kanban --board project-board watch
hermes wingstaff status stable-workflow-id
```

The gateway's Kanban dispatcher executes ready cards. The start command creates
the graph; it does not start a second scheduler, daemon, or nested agent.

## Approve the exact plan

Approval remains bound to the SHA-256 digest recorded on the current plan
artifact:

```bash
hermes wingstaff approve <workflow-id> <64-character-plan-digest>
```

Do not copy a digest from an older plan revision. A mismatch fails without
authorizing work. Generic `hermes kanban unblock` is not approval. Successful
approval completes the blocked gate and creates
`implement → verify → review → deliver` in one persistent worktree.

## Cancel

Cancellation requires an audit reason:

```bash
hermes wingstaff cancel <workflow-id> "Superseded by a different change"
```

Cancellation comments and archives the workflow's cards through public Hermes
operations and cleans only its Wingstaff-owned worktree. The policy and artifact
ledger remains available for diagnostics.

## Recovery

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
hermes plugins update wingstaff
hermes wingstaff doctor
hermes wingstaff packs check addyosmani
```

Do not widen the documented Hermes compatibility range based only on a successful
install. A new host version requires the repository's plugin-load, CLI, test,
build, and clean-install probes.

## Standalone diagnostics

The following forms are intentionally equivalent and return the same JSON and
exit code:

```bash
hermes wingstaff status <workflow-id>
wingstaff status <workflow-id>
```

Use the native form operationally. The standalone executable exists for package
smoke tests and diagnostics, not as a separate orchestration runtime.
