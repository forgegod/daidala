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

Coordinate a pack-defined software-development lifecycle using Hermes' existing tools. Wingstaff does not start another server or call nested Hermes processes.

## When to Use

Load this skill explicitly as `wingstaff:orchestrate` when starting or resuming a Wingstaff workflow.

## Procedure

1. Call `wingstaff_pack_info` for the selected pack. Choose an existing named
   Kanban board, an explicit stable workflow ID, and a complete mapping from
   every executable stage to an existing Hermes profile.
2. Call `wingstaff_start` with that board, workflow ID, stage-profile mapping,
   absolute local repository path, and explicit goal. Start validates the clean
   repository baseline, exact skills, and profiles before it creates the linked
   definition and plan cards. Stop on any validation or host error.
3. Produce the definition with the pack's `define` skills and pass the complete
   Markdown to `wingstaff_submit_artifact` with `stage: "define"`.
4. Produce the complete plan with the pack's `plan` skills and pass it to
   `wingstaff_submit_artifact` with `stage: "plan"`.
5. Read the returned plan artifact and digest. Present the plan, risks, scope,
   and verification criteria to the human. Do not call an implementation tool
   until the human explicitly approves that exact digest.
6. After approval, call `wingstaff_approve` with the returned plan digest, then
   call `wingstaff_prepare_implementation`. Hermes Kanban dispatches the
   configured implementation profile in the returned persistent `worktree_path`;
   retries reuse the same implementation card.
7. Load the `implement` skills and use normal Hermes `read_file`, `search_files`,
   `patch`, `write_file`, and `terminal` tools in the worktree. Do not commit or
   push target changes.
8. Call `wingstaff_capture_implementation`. It must return a real, non-empty
   diff artifact before verification can begin.
9. Run every plan verification command through Hermes' `terminal` tool with the
   worktree as `workdir`. Immediately pass the exact command, exit code, and
   output to `wingstaff_record_verification`. A non-zero exit blocks the
   workflow; do not fabricate a passing retry.
10. Read the captured diff and verification evidence, run the pack's `review`
    skills, and submit the review with `wingstaff_submit_artifact` using
    `stage: "review"`.
11. Call `wingstaff_deliver`. Report its changed paths, diff path, and
    verification evidence. The delivery explicitly records `committed: false`
    and `pushed: false`; separate authorization is required for either action.
12. Use `wingstaff_status` to resume from durable state after interruption.

## Common Pitfalls

- Treating a listed skill name as proof that the exact skill is installed.
- Writing implementation files in the target checkout instead of the returned
  Wingstaff worktree.
- Starting implementation before digest-bound human approval.
- Recomputing delivery scope after verification instead of using the captured
  implementation snapshot.
- Reporting model prose as verification evidence.
- Committing or pushing target changes as part of delivery.
- Spawning a new MCP, HTTP service, or nested `hermes chat` process.

## Verification Checklist

- [ ] Pack and every exact skill validated.
- [ ] Clean baseline commit recorded.
- [ ] Define and plan artifacts exist.
- [ ] Human approval matches the current plan digest.
- [ ] Implementation ran only in the returned fresh worktree.
- [ ] Captured implementation diff is non-empty.
- [ ] Verification command, exit code, and output reference are durable.
- [ ] Review artifact exists after passing verification.
- [ ] Delivery reports changed paths without a target commit or push.
