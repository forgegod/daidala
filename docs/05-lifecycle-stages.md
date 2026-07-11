# 05 — Lifecycle stages

The executable lifecycle is a Hermes Kanban card graph. Wingstaff validates
policy and records evidence; it does not call a model, start another agent
process, publish a competing task status, or automatically commit and push
target changes.

The approval-gated graph, stage worker handoff/recovery contract, and native and
standalone operator-command paths are implemented.

## Stage contract

| Card | Input | Durable handoff | Hermes result |
|---|---|---|---|
| Define | Goal, pack, exact skills, clean baseline | `define.md` path and digest | Complete or block |
| Plan | Definition handoff | `plan.md` path and digest | Complete or block |
| Approval | Current plan digest | Approval actor, time, and digest | Remain blocked until Wingstaff approval; then complete |
| Implement | Approved revision and absolute owned worktree | Captured diff and changed-path manifest | Complete or block |
| Verify | Immutable implementation scope and exact commands | Commands, exit codes, and output references | Complete or block |
| Review | Captured diff and passing evidence | Review artifact and decision | Complete or block |
| Deliver | Approved review and immutable evidence | `delivery.json` with `committed: false`, `pushed: false` | Complete or block |

## Graph creation and assignment

1. The caller selects an existing named board, one default Hermes profile, and
   optional per-stage profile overrides.
2. Wingstaff expands and persists the complete stage-to-profile mapping, then
   validates every profile before creating cards.
3. `wingstaff_start` creates `define` and dependent `plan` with the bundled
   `wingstaff:orchestrate` worker contract, exact pack skills, and deterministic
   idempotency keys.
4. After the plan handoff, Wingstaff records its digest and creates a blocked
   approval card linked from `plan`.
5. `hermes wingstaff approve <workflow-id> <digest>` records exact approval.
   The command annotates and completes the gate through documented host
   operations; generic `hermes kanban unblock` does not satisfy Wingstaff policy.
6. Wingstaff creates `implement → verify → review → deliver` only after approval.
   Every card uses its resolved profile, the bundled worker contract, exact stage
   skills, real parent links, and the same absolute Wingstaff-owned worktree.

`wingstaff_status` is read-only and combines ledger facts with live Kanban card
data. Cancellation cleans Wingstaff-owned resources and uses documented Kanban
operations; card lifecycle remains visible on the board.

## Skill activation before evidence

Every executable worker follows the same ordering:

```text
kanban_show
    -> inspect parent artifacts and pinned skill criteria
    -> wingstaff_record_skill_activation
    -> apply active methodology
    -> stage evidence operation
    -> kanban_complete with activation digest + active skill names
```

The card still loads `wingstaff:orchestrate` and the full exact pack-stage skill
set. Loaded pack skills are candidates, not proof that every skill applies.
`required` is pack policy; `conditional` permits worker judgment. The immutable
activation artifact records applicable, deferred, not-applicable, or blocked
decisions with criteria, evidence, rationale, and applicable-skill rank.

Wingstaff accepts each stage's artifact, implementation capture, verification
record, review, or delivery only when the current stage/revision has a finalized,
unblocked activation reference. Missing and pending references fail closed. A
blocked manifest remains durable for audit, but the worker comments with its
digest and blocked skill and blocks the Kanban card without a completion handoff.
A deferred skill whose condition occurs requires a superseding manifest before
evidence submission.

## Human gate

No worktree or post-gate card is created before approval. Approval binds the
entire current plan artifact, not a task subset. Changing the plan invalidates
approval, increments the graph revision, and prevents evidence submission from
the previous graph.

## Implementation isolation

Implementation runs in a detached Wingstaff-owned Git worktree created at the
recorded baseline commit. The original target checkout stays unchanged.
Immediately after implementation, Wingstaff captures:

- a binary-capable diff, including untracked implementation files;
- the changed-path set before verification creates caches or build products.

Verification and delivery use that immutable snapshot. An empty implementation
diff cannot advance.

## Blocking and recovery

Every worker starts with `kanban_show` and ends with `kanban_complete` or
`kanban_block`. Before blocking, it writes a concise comment with `workflow_id`,
stage, pack revision, artifact or worktree references, exact command evidence,
the activation digest and blocked skill when relevant, and the decision required.

- Missing dependency uses `kind: dependency`; Hermes returns the card to `todo`
  and promotes it when parents complete.
- Missing access or host capability uses `kind: capability`.
- Verification or review feedback uses `kind: needs_input` with a
  `verification-failed:` or `review-required:` reason.
- A genuinely flaky host failure uses `kind: transient`; deterministic test
  failures are not transient.

A human comments with the decision or remediation, may reassign the blocked
card to an implementation-capable profile, and unblocks it. Hermes respawns the
card with its full thread and the same preserved worktree. Wingstaff does not
rewind or mirror a private status.

The implementation diff is immutable after capture. Verification and review may
retry or request input in the preserved worktree, but they must not change its
captured implementation scope. Required code changes replace the plan and use a
new digest-bound approval and graph revision.

## Delivery boundary

Delivery reports the baseline, captured changed paths, and verification
evidence. It records `committed: false` and `pushed: false`. Committing or
pushing the target requires a separate future authorization surface.

## Source of truth

- Contract: this document and the active Kanban-native implementation plan
- Schemas and handlers: `wingstaff/schemas.py`, `wingstaff/tools.py`
- Policy service and graph adapter: `wingstaff/service.py`,
  `wingstaff/kanban.py`
- Preserved artifact and worktree operations: `wingstaff/execution.py`
- Target worker procedure: `wingstaff/skills/orchestrate/SKILL.md`
- Graph verification: `tests/test_execution.py`, Kanban adapter tests,
  and an isolated end-to-end host probe
