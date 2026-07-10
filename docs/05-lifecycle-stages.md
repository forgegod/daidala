# 05 — Lifecycle stages

The executable lifecycle is driven by Hermes through Wingstaff's JSON tools.
Wingstaff records explicit outputs and enforces order; it does not call a model,
start another agent process, or automatically commit and push target changes.

## Stage contract

| Stage | Input | Durable output | Next state |
|---|---|---|---|
| Discover | Absolute local repository and goal | Workflow identity | `draft` |
| Define | Valid pack, exact installed skills, clean baseline | `define.md` and digest | `running/plan` |
| Plan | Complete definition | `plan.md` and digest | `awaiting_approval` |
| Approve | Human decision and exact plan digest | Approval record | `approved` |
| Implement | Approved plan, unchanged baseline, and assignee profile | Detached worktree, idempotent Kanban card, and captured `implementation.diff` | `running/verify` |
| Verify | Command, exit code, and exact output | `verification.txt` and structured evidence | `running/review` or `blocked` |
| Review | Captured implementation scope and passing evidence | `review.md` and digest | `running/deliver` |
| Deliver | Reviewed immutable implementation snapshot | `delivery.json` | `completed` |

## Tool sequence

1. `wingstaff_start`
2. `wingstaff_validate`
3. `wingstaff_submit_artifact` with `stage: "define"`
4. `wingstaff_submit_artifact` with `stage: "plan"`
5. present the complete plan and wait for explicit human approval
6. `wingstaff_approve` with the current plan digest
7. `wingstaff_prepare_implementation` with an existing Hermes profile as `assignee`
8. let Hermes Kanban dispatch that profile in the persistent `worktree_path`
9. `wingstaff_capture_implementation`
10. run verification through Hermes' `terminal` tool in the worktree
11. `wingstaff_record_verification` with the exact result
12. `wingstaff_submit_artifact` with `stage: "review"`
13. `wingstaff_deliver`

`wingstaff_status` is read-only and may be called at every point. A nonterminal
workflow may be stopped with `wingstaff_cancel`.

## Human gate

No worktree is created before approval. Approval binds the entire current plan
artifact, not a task subset. Changing the plan invalidates approval and returns
the workflow to `awaiting_approval`.

## Implementation isolation

Implementation runs in a detached Wingstaff-owned Git worktree created at the
recorded baseline commit. The original target checkout stays unchanged.
Immediately after implementation, Wingstaff captures:

- a binary-capable diff, including untracked implementation files;
- the changed-path set before verification creates caches or build products.

Verification and delivery use that immutable snapshot. An empty implementation
diff cannot advance.

## Verification and blocking

Hermes runs the plan's real commands through its normal `terminal` tool.
Wingstaff stores the command, integer exit code, output reference, and timestamp.
Exit code zero advances to review. Any non-zero exit makes the workflow terminal
`blocked`; review and delivery cannot proceed.

## Delivery boundary

Delivery reports the baseline, captured changed paths, and verification
evidence. It records `committed: false` and `pushed: false`. Committing or
pushing the target requires a separate future authorization surface.

## Source of truth

- Schemas and handlers: `wingstaff/schemas.py`, `wingstaff/tools.py`
- Lifecycle service: `wingstaff/service.py`
- Artifact and worktree operations: `wingstaff/execution.py`
- State transitions: `wingstaff/workflow.py`
- Procedure: `wingstaff/skills/orchestrate/SKILL.md`
- Executable fixture: `tests/test_execution.py`
