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

Start requires a clean local Git repository and a concrete goal:

```bash
hermes wingstaff start /absolute/path/to/repository "Implement the approved change"
```

The command creates and validates durable workflow state, then prints JSON
containing the workflow ID. Continue planning and artifact submission in a
Hermes session with the bundled `wingstaff:orchestrate` skill and Wingstaff
tools. Resume operator inspection at any time with:

```bash
hermes wingstaff status <workflow-id>
```

Status reads the SQLite authority; Kanban is not used as workflow state.

## Approve the exact plan

Approval is bound to the SHA-256 digest recorded on the current plan artifact:

```bash
hermes wingstaff approve <workflow-id> <64-character-plan-digest>
```

Do not copy a digest from an older plan revision. A mismatch fails without
advancing the workflow. After approval, the orchestration skill prepares the
persistent worktree and idempotently dispatches the implementation card.

## Cancel

Cancellation requires an audit reason:

```bash
hermes wingstaff cancel <workflow-id> "Superseded by a different change"
```

Cancellation is terminal. Start a new workflow instead of trying to reopen it.

## Recovery

Wingstaff transitions and Hermes cards are retry-safe at their boundary:

1. Run `hermes wingstaff status <workflow-id>` to inspect durable state.
2. If implementation state exists but no worker card is visible, resume the
   orchestration skill and retry implementation preparation. The same
   `wingstaff:<workflow-id>:implement` idempotency key prevents duplicates.
3. If a card is blocked, inspect the Hermes Kanban error. Missing assigned-profile
   skills must be installed in that profile; Wingstaff does not cross-read or
   mutate another profile's skill store.
4. If verification failed, preserve its structured evidence and correct the
   target worktree. Never fabricate replacement evidence.
5. A blocked or cancelled workflow is terminal. Start a new workflow when the
   underlying request remains valid.

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
