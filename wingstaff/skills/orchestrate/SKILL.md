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

1. Call `wingstaff_pack_info` for the selected pack.
2. Stop if the pack or any required skill cannot be resolved.
3. Produce explicit artifacts for the `define` and `plan` stages.
4. Present the plan, risks, scope, and verification criteria to the human.
5. Do not create implementation work until the human explicitly approves.
6. After approval, execute `implement`, `verify`, `review`, and `deliver` in order.
7. Treat failed verification as a blocked workflow. Do not replace it with guessed output.
8. Deliver paths, commands, and real verification results.

## Common Pitfalls

- Treating a listed skill name as proof that the skill was loaded.
- Starting implementation before approval.
- Reporting model prose as verification evidence.
- spawning a new MCP or HTTP service instead of using Hermes facilities.

## Verification Checklist

- [ ] Pack validated.
- [ ] Required skills resolved by exact name.
- [ ] Define and plan artifacts exist.
- [ ] Human approval recorded before implementation.
- [ ] Tests or equivalent checks executed.
- [ ] Delivery includes real paths and command results.
