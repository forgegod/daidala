# Getting started with Wingstaff

This walkthrough starts one Wingstaff workflow from the native Hermes CLI and
follows it through the digest-bound approval gate. Wingstaff creates the graph;
the Hermes gateway's Kanban dispatcher executes ready cards.

## 1. Check the prerequisites

Use Hermes Agent v0.18.2, the only verified host version. The target must be a
clean local Git repository. Run these commands in the Hermes profile that will
own the workflow:

```bash
hermes plugins install forgegod/hermes-wingstaff --enable
hermes plugins list
hermes wingstaff doctor --pack aidlc
```

`doctor` is read-only. For the Addyosmani pack, preview and then explicitly apply
its pinned external-skill installation plan:

```bash
hermes wingstaff packs install addyosmani
hermes wingstaff packs install addyosmani --apply
hermes wingstaff packs check addyosmani
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
Kanban dispatcher that claims ready cards; Wingstaff has no dispatcher loop of
its own.

## 3. Start explicitly

```bash
hermes wingstaff start /absolute/path/to/repo "Implement the requested change" \
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

Do not use `--profile`; Hermes consumes that host-level option before the plugin
subcommand parser receives it. Override individual stages only when needed:

```bash
--stage-profile define=architect --stage-profile review=reviewer
```

Observable result: Wingstaff records the clean baseline and creates linked
`define → plan` cards with deterministic idempotency keys. Repeating the same
start command returns the same workflow and cards.

## 4. Observe definition and planning

Use normal Hermes surfaces:

```bash
hermes kanban --board project-board watch
hermes kanban --board project-board list --json
hermes wingstaff status first-workflow
```

The worker first calls `kanban_show`, uses the skills pinned to its card, records
its artifact through a Wingstaff evidence tool, and completes with structured
`wingstaff.handoff/v1` metadata. The `plan` card becomes runnable after `define`
completes.

After planning, Wingstaff creates an approval card in `blocked` state. No
implementation-capable card exists yet.

## 5. Approve the exact plan

Read the plan artifact and its 64-character SHA-256 digest. Approve only after
the plan, risks, scope, and verification criteria are acceptable:

```bash
hermes wingstaff approve first-workflow <64-character-plan-digest>
```

A stale or changed digest fails closed. `hermes kanban unblock` only changes a
card interaction state and never satisfies Wingstaff approval policy. Successful
approval records the exact digest, creates one detached worktree, completes the
gate, and creates:

```text
implement → verify → review → deliver
```

## 6. Follow execution and delivery

All post-gate cards share the Wingstaff-owned worktree. Hermes Kanban owns their
status, assignment, dependencies, retry history, comments, and runs. Wingstaff
owns the captured implementation scope and evidence:

- `implement`: immutable diff and changed-path manifest;
- `verify`: exact commands, exit codes, and content-addressed outputs;
- `review`: decision against the captured diff and evidence;
- `deliver`: reviewed references with `committed: false` and `pushed: false`.

Inspect a card or combined workflow status with:

```bash
hermes kanban --board project-board show <card-id> --json
hermes wingstaff status first-workflow
```

Delivery does not commit or push the target repository.

## 7. Recover or cancel

For a blocked worker, read its comment and run history, correct the prerequisite,
comment with the human decision, and unblock the same card:

```bash
hermes kanban --board project-board comment <card-id> "Remediation completed"
hermes kanban --board project-board unblock <card-id> --reason "Retry approved"
```

The dispatcher respawns the card with its thread and persistent workspace.
Verification and review must not mutate an already captured implementation; code
changes require a new plan digest and approval revision.

Cancel Wingstaff-owned resources explicitly:

```bash
hermes wingstaff cancel first-workflow "Superseded by another change"
```

This comments and archives the workflow cards and removes only the Wingstaff-owned
worktree. The policy and artifact ledger remains available for diagnostics.

## Trigger and runtime boundary

Wingstaff does not create cron jobs. A workflow starts through an explicit
`hermes wingstaff start` command or an agent call to `wingstaff_start`. Cron may
optionally prompt an agent to perform that same action, but it is external to
Wingstaff and does not replace the gateway dispatcher.

Hermes issue
[#34977](https://github.com/NousResearch/hermes-agent/issues/34977) concerns the
global orchestrator profile used by host goal decomposition. Wingstaff does not
use that routing path: it selects a board, expands a complete explicit
stage-to-profile map, and creates each card directly. Native and standalone CLI
processes use documented `hermes kanban` subprocess operations; agent-facing
tools use the in-process plugin tool registry. Both produce the same graph.

## Next references

- [Operator runbook](07-runbook.md)
- [Architecture and authority split](01-architecture.md)
- [Lifecycle stages and handoffs](05-lifecycle-stages.md)
- [Hermes compatibility boundary](08-hermes-integration.md)
