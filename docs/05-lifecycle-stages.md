# 05 — Lifecycle stages

The executable lifecycle is a Hermes Kanban card graph. Daidala validates
policy and records evidence; it does not call a model, start another agent
process, publish a competing task status, or let a worker commit or push target
changes. A separate attended branch-delivery adapter may commit and push only
after its own exact preview and confirmation gates.

The approval-gated graph, stage worker handoff/recovery contract, and native and
standalone operator-command paths are implemented.

## Stage contract

Every executable stage requires a current, finalized, unblocked skill activation
manifest before Daidala records its durable handoff. Plan approval and attended
review disposition are ledger gates, not executable cards, and have no activation
manifest. Replacing a plan increments the revision, clears approval, and requires
a new matching approval before post-gate work can proceed.
Every executable card also binds the current policy revision and nullable
constraint identity. Constraint replacement archives stale cards, preserves
historical artifacts plus verification/review/disposition history, and restarts
at `define` before renewed tuple approval.

| Card | Input | Durable handoff | Hermes result |
|---|---|---|---|
| Define | Goal, pack, exact skills, clean baseline | `define.md` path and digest | Complete or block |
| Plan | Definition handoff | `plan.md` path and digest | Complete or block |
| Approval | Current plan and nullable constraint revision/digest tuple | Approval actor, time, and exact tuple | Ledger-only human gate; no Kanban card |
| Implement | Approved revision and absolute owned worktree | Captured diff and changed-path manifest | Complete or block |
| Verify | Immutable implementation scope and exact commands | Commands, exit codes, and output references | Complete or block |
| Review | Captured diff and passing evidence | Structured outcome, summary, bounded findings, exact review digest | Accepted evidence completes; other outcomes comment and block |
| Disposition | Exact current review, implementation, verification, plan, policy, and constraint tuple | Attended action, actor, rationale, and exact digest binding | Ledger-only human gate; no Kanban card |
| Deliver | Exact attended acceptance of an accepted, non-blocking review | Adapter-owned receipt naming reviewed branch, commit, remote ref, and authorization digest | Completed only by the attended adapter or remains pending |

## Graph creation and assignment

1. The caller selects an existing named board, one default Hermes profile, and
   optional per-stage profile overrides.
2. Daidala expands and persists the complete stage-to-profile mapping, then
   validates every profile before creating cards.
3. `daidala_start` creates `define` and dependent `plan` with the bundled
   `daidala:orchestrate` worker contract, exact pack skills, and deterministic
   idempotency keys of the form
   `daidala:<workflow-id>:<plan-revision>:<policy-revision>:<constraint-digest-or-none>:<stage>`.
4. After the plan handoff, Daidala records its digest and exposes the exact
   pending approval tuple from the ledger without creating a Kanban card.
5. `hermes daidala approve <workflow-id> <digest>` records exact attended
   approval. Kanban workers are rejected, and generic `hermes kanban unblock`
   does not satisfy Daidala policy.
6. Daidala creates `implement → verify → review` only after plan approval.
   `implement` is parented directly from `plan`; every post-gate card uses its
   resolved profile, bundled worker contract, exact stage skills, real parent
   links, and the same absolute Daidala-owned worktree.
   A Git-pinned imported plan starts from the same approval gate but creates no
   synthetic `define` or `plan` card; its unparented `implement` card remains
   bound to the persisted packet digest and immutable copied plan artifact.
   Its workers never edit the active source plan path; a scope finding blocks for
   attended action and, when required, a separately committed successor source.
7. Automated review records evidence but creates no delivery card. An attended
   exact-digest `accept-delivery` decision creates `deliver`; `request-revision`
   preserves the source tuple and creates one revision-addressed Plan card;
   `reject-workflow` cancels the workflow.

`daidala_status` is read-only and combines ledger facts with live Kanban card
data. Cancellation cleans Daidala-owned resources and uses documented Kanban
operations; card lifecycle remains visible on the board.

## Terminal artifact eligibility

Artifact curation never decides workflow completion. A delivered workflow is
eligible only when its current delivery evidence verifies and no Daidala-owned
worktree remains. An abandoned workflow is eligible only when every recorded
Kanban card can be read and is terminal (`done` or `archived`). Missing host
state, ledger drift, a nonterminal card, an owned worktree, or unverifiable
artifact bytes blocks the transition.

The first verified terminal observation starts the deterministic age clock.
Configured stale and archive thresholds may advance unpinned workflows, while a
pin prevents automatic archive. Archive publication verifies the manifest and
all artifact digests before source cleanup; retries converge from active-only,
dual-copy, archive-only, or partial-cleanup states. Curation changes storage
availability only—it does not mutate the immutable ledger artifact identity or
Hermes card lifecycle.

## Skill activation before evidence

Every executable worker follows the same ordering:

```text
kanban_show
    -> inspect parent artifacts and pinned skill criteria
    -> daidala_record_skill_activation
    -> apply active methodology
    -> stage evidence operation
    -> kanban_complete with activation digest + active skill names
```

The card still loads `daidala:orchestrate` and the full exact pack-stage skill
set. Loaded pack skills are candidates, not proof that every skill applies.
`required` is pack policy; `conditional` permits worker judgment. The immutable
activation artifact records applicable, deferred, not-applicable, or blocked
decisions with criteria, evidence, rationale, and applicable-skill rank.

Daidala accepts each worker stage's artifact, implementation capture, verification
record, or review only when the current stage/revision has a finalized, unblocked
activation reference. Missing and pending references fail closed. A
blocked manifest remains durable for audit, but the worker comments with its
digest and blocked skill and blocks the Kanban card without a completion handoff.
A deferred skill whose condition occurs requires a superseding manifest before
evidence submission.

## Human gate

No worktree or post-gate card is created before approval. Approval binds the
entire current plan artifact, not a task subset. Imported-plan approval also
binds the exact Git source-packet digest; only fresh preview/apply admission may
create that source, and local plan replacement is rejected. Changing a generated
plan invalidates approval, increments the graph revision, and prevents evidence
submission from the previous graph.

After imported-plan delivery, the attended adapter records the exact reviewed
branch, commit, and remote ref only when the committed manifest enables delivery.
Otherwise delivery remains blocked; it never falls back to a direct checkpoint.
The Deliver card's single completed run must contain the same non-secret
branch/commit receipt before a replay may release the owned worktree. Any other
completed-run metadata fails closed rather than being treated as delivery
authority.
Any later `start-from-plan` request still requires a separately admitted source
packet and fresh approval; the earlier packet and approval are historical
evidence only.

Automated review is not delivery authority. Attended disposition binds the exact
current review and all evidence identities. `accept_delivery` requires an
accepted review with no blocking findings. A stale tuple or Kanban-worker caller
fails without mutation. Reviewer disagreement without changed code stays on the
review card through comment/unblock; it does not override a blocking finding or
grant disposition authority.

## Implementation isolation

Implementation runs in a detached Daidala-owned Git worktree created at the
recorded baseline commit. The original target checkout stays unchanged.
Immediately after implementation, Daidala captures:

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
card with its full thread and the same preserved worktree. Daidala does not
rewind or mirror a private status.

`daidala_capture_implementation` captures the implementation diff before
verification; that pre-verification snapshot is immutable. Verification and
review may retry or request input in the preserved worktree, but they must not
change its captured scope. Required code, verification-scope, or approach changes
use attended `request-revision`: Daidala writes the canonical request and
successor packet before archive or worktree cleanup, preserves prior evidence,
creates Plan revision N+1, and requires a newly recorded plan plus fresh approval.
There is no direct phase rewind.

## Delivery boundary

The delivery card is created lazily and idempotently only after exact attended
acceptance. It has no worker operation. The attended CLI/dashboard adapter
revalidates the baseline, pre-verification captured paths, review, disposition,
verification evidence, committed manifest, trusted registration, release flags,
derived `daidala/<workflow-id>` branch, credential availability, and fresh
preview digest. Only then can its literal confirmation commit the reviewed diff,
push that branch, record the remote-ref receipt, complete Deliver, and release
the owned worktree. It rejects drift, missing credentials, a conflicting remote
branch, and non-derived branches without mutation. For Git-pinned phases, later
admission still requires a separately admitted source packet and fresh approval.

The dashboard renders the exact review evidence and attended preview-confirm
disposition over the same service authority as the native CLI. A revision request
returns to the successor exact-plan approval decision; it never rewinds a phase or
mutates the rejected captured diff in place.

## Source of truth

- Contract: this document
- Schemas and handlers: `daidala/schemas.py`, `daidala/tools.py`
- Policy service and graph adapter: `daidala/service.py`,
  `daidala/kanban.py`
- Preserved artifact and worktree operations: `daidala/execution.py`
- Target worker procedure: `daidala/skills/orchestrate/SKILL.md`
- Graph verification: `tests/test_execution.py`, Kanban adapter tests,
  and an isolated end-to-end host probe
