---
name: orchestrate
description: Use when running a software-development workflow through Wingstaff. Enforces pack validation, explicit artifacts, a pre-implementation human gate, and evidence-backed completion.
version: 0.1.0
author: Wingstaff
license: MIT
metadata:
  hermes:
    tags: [software-development, orchestration, human-in-the-loop]
---

# Wingstaff Orchestrate

## Overview

Coordinate a pack-defined software-development lifecycle on Hermes Kanban. This
skill has two entry modes: a launcher explicitly starts or resumes a workflow;
each dispatcher-spawned stage worker follows the card-scoped worker contract.
Wingstaff does not start another server or call nested Hermes processes.

## When to Use

Load this skill explicitly as `wingstaff:orchestrate` when starting or resuming a
workflow. Wingstaff also pins it to every executable stage card so a worker does
not depend on the launcher session retaining these instructions.

## Launch or Resume

1. Call `wingstaff_pack_info` for the selected pack. Choose an existing named
   Kanban board, an explicit stable workflow ID, and a complete mapping from
   every executable stage to an existing Hermes profile.
2. Call `wingstaff_start` with that board, workflow ID, stage-profile mapping,
   absolute local repository path, explicit goal, and any operator-selected
   `constraints_content` or exact `constraints_skill` plus
   `constraints_skill_digest`. Never infer a policy source. Start validates the
   clean repository baseline, exact skills, policy source, and profiles before
   it creates the linked definition and plan cards. Stop on any validation or
   host error.
3. Stop launching. Hermes Kanban dispatches `define` and promotes the linked
   cards as their parents complete. Use `wingstaff_status` and normal Kanban
   surfaces to inspect or resume; do not execute stage work in the launcher.
4. When the plan worker completes, present the plan, risks, scope, verification
   criteria, and returned digest to the human. Do not approve until the human
   explicitly accepts that exact digest.
5. Call `wingstaff_approve` with the accepted digest. This records approval,
   creates the persistent worktree, completes the blocked gate, and creates the
   linked post-gate cards. Do not call `wingstaff_prepare_implementation`
   separately unless recovery diagnostics show the approved worktree is absent.

## Stage Worker Contract

1. Call `kanban_show` before any file, terminal, or Wingstaff tool. Treat its
   worker context, parent handoffs, prior attempts, and comments as the task
   input. Confirm the card body names the expected workflow ID, stage, pack, and
   plan revision, policy revision, constraint revision and digest. Compare that
   identity with the current Wingstaff status before applying methodology or
   submitting evidence. Block with `kind: capability` if context is missing,
   stale, or contradictory; never continue from a superseded card.
2. Treat `wingstaff:orchestrate` as always required and every other skill pinned
   to the card as a pack-declared candidate. Do not call `wingstaff_pack_info`,
   discover replacement skills, install skills, or re-derive the stage mapping.
3. Inspect the relevant parent artifacts and classify every candidate against
   its pinned `Use When`, `When NOT to Use`, capability requirements, the card,
   parent handoffs, and this stage policy. Then call
   `wingstaff_record_skill_activation` before applying stage methodology or
   producing evidence. Loaded candidates are not automatically active.
4. Work only in `HERMES_KANBAN_WORKSPACE`. For post-gate cards, confirm it equals
   the absolute persistent worktree in the card body. Never edit the original
   target checkout.
5. Apply every global constraint and only the current stage's phase constraints.
   Block rather than weakening conflicting policy or treating methodology-like
   constraint text as executable instructions.
6. Use Wingstaff tools only for policy and evidence operations. Hermes Kanban
   remains the only lifecycle authority.
7. End every run with exactly one `kanban_complete` or `kanban_block` call. A
   prose response is not completion. Use `kanban_heartbeat` during long work.

### Skill Activation

Pack policy and worker judgment are separate:

- `required` means the pack requires the skill. Record it as `applicable`, or
  `blocked` when a missing capability or stage-policy conflict prevents use;
  never demote it to another category.
- `conditional` means the worker chooses `applicable`, `deferred`,
  `not_applicable`, or `blocked` from the pinned criteria and current evidence.
- `applicable` skills are active now. Give them unique contiguous ranks starting
  at 1 in attention order.
- `deferred` skills are inactive until a precise recorded condition occurs. If
  it occurs, record a superseding manifest that makes the skill `applicable` or
  `blocked` before submitting stage evidence.
- `not_applicable` means current task evidence or negative criteria exclude the
  skill.
- `blocked` means a required or relevant skill cannot be applied. Persist the
  manifest, comment with its digest and every blocked skill, then call
  `kanban_block(kind: "capability")`. Do not fabricate a successful handoff.

Every decision cites non-empty matched criteria, task evidence, and rationale.
Only `deferred` has a non-empty condition; only `applicable` has a rank. Keep the
returned activation digest for the handoff or blocking comment.

### Stage Operations

| Stage | Required Wingstaff operation | Successful Kanban result |
|---|---|---|
| `define` | Submit the complete definition with `wingstaff_submit_artifact(stage: "define")`. | Complete with the definition artifact reference and digest. |
| `plan` | Submit the complete plan with `wingstaff_submit_artifact(stage: "plan")`. | Complete with the plan reference and digest; implementation still waits for exact human approval. |
| `implement` | Apply only the approved plan in the persistent worktree, then call `wingstaff_capture_implementation`. | Complete with the immutable diff and changed-path references. |
| `verify` | Run every approved command in the persistent worktree and immediately call `wingstaff_record_verification` with the exact command, exit code, and output. | Complete only when the final evidence passes; otherwise comment and block. |
| `review` | Review the captured diff and verification evidence without changing files, then submit the decision with `wingstaff_submit_artifact(stage: "review")`. | Complete only for an accepted review; otherwise comment and block. |
| `deliver` | Call `wingstaff_deliver` and inspect its durable delivery artifact. | Complete with changed paths and evidence references, explicitly reporting `committed: false` and `pushed: false`. |

Implementation scope is immutable after `wingstaff_capture_implementation`.
Verification and review workers must not modify it. If review or deterministic
verification reveals required code changes, comment and block; the operator must
replace the plan and create a new approved graph revision rather than patching a
captured diff in place.

## Structured Handoff

Successful workers call `kanban_complete` with a concise summary and metadata
using schema `wingstaff.handoff/v1`. Metadata must contain:

- `schema`, `workflow_id`, `plan_revision`, `policy_revision`,
  `constraints_revision`, `constraints_digest`, `stage`, `pack`, `pack_revision`,
  `outcome`, `artifact_refs`, `skill_activation_digest`, and `active_skills`;
- `workspace_path` and `baseline_commit` for `implement`, `verify`, `review`, and
  `deliver`;
- diff and changed-path manifest references for `implement`;
- exact commands, exit codes, and output references for `verify`;
- the review decision for `review`;
- the delivery artifact and its `committed: false`, `pushed: false` restrictions
  for `deliver`.

Use artifact references and digests, not large artifact bodies or raw logs. Keep
credentials, tokens, and unrelated transcripts out of comments and metadata.

## Blocking and Recovery

Before `kanban_block`, call `kanban_comment` with the workflow ID, stage, plan
revision, relevant evidence references, what happened, and the exact decision or
remediation required. Then choose the narrowest supported kind:

- `dependency` for an unfinished prerequisite;
- `capability` for missing tools, skills, access, or valid worker context;
- `needs_input` with a `verification-failed:` or `review-required:` reason for
  deterministic verification or review feedback;
- `transient` only for genuinely flaky host failures.

A human comments with the decision or remediation and unblocks the same card.
On retry, call `kanban_show` again, read the full thread and prior attempts, and
reuse the preserved workspace and idempotent Wingstaff evidence. Never infer
approval from a generic unblock. A changed plan requires a new digest-bound
approval and graph revision.

## Common Pitfalls

- Treating a listed skill name as proof that the exact skill is installed.
- Shelling out to `hermes kanban` from a worker instead of using task-scoped
  `kanban_*` tools.
- Exiting without `kanban_complete` or `kanban_block`.
- Writing implementation files in the target checkout instead of the returned
  Wingstaff worktree.
- Starting implementation before digest-bound human approval.
- Treating every loaded candidate skill as active without recording an
  activation decision.
- Submitting evidence with a missing, pending, or blocked activation manifest.
- Applying a deferred skill after its condition occurs without first recording
  a superseding manifest.
- Recomputing delivery scope after verification instead of using the captured
  implementation snapshot.
- Modifying the worktree during verification or review after the implementation
  snapshot was captured.
- Reporting model prose as verification evidence.
- Committing or pushing target changes as part of delivery.
- Spawning a new MCP, HTTP service, or nested `hermes chat` process.

## Verification Checklist

- [ ] Pack and every exact skill validated.
- [ ] Worker called `kanban_show` first and used the card's pinned skills.
- [ ] Worker recorded a finalized, unblocked skill activation manifest before
      stage methodology and evidence.
- [ ] Successful handoff contains the activation digest and active skill names.
- [ ] Clean baseline commit recorded.
- [ ] Define and plan artifacts exist.
- [ ] Human approval matches the current plan digest.
- [ ] Implementation ran only in the returned fresh worktree.
- [ ] Captured implementation diff is non-empty.
- [ ] Verification command, exit code, and output reference are durable.
- [ ] Review artifact exists after passing verification.
- [ ] Delivery reports changed paths without a target commit or push.
- [ ] Every worker run ended through `kanban_complete` or `kanban_block` with a
      durable `wingstaff.handoff/v1` handoff or blocking comment.
