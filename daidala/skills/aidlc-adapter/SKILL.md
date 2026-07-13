---
name: aidlc-adapter
description: Apply the pinned AI-DLC v1.0.1 methodology inside Wingstaff's lifecycle without importing AI-DLC's runtime or state machine.
metadata:
  wingstaff:
    upstream: https://github.com/awslabs/aidlc-workflows
    revision: e49341dbeb8af82758dd85e96ed7fe9bcf38a447
    release: v1.0.1
    license: MIT-0
---

# AI-DLC adapter

Use AI-DLC's adaptive development concepts as judgment guidance while Wingstaff remains authoritative for state, approval, worktrees, verification evidence, and delivery.

## Stage mapping

- `define`: perform inception-style intent analysis. Produce the Wingstaff definition artifact with requirements, constraints, ambiguities, and acceptance criteria. Do not create a separate AI-DLC state file.
- `plan`: map useful inception and construction decisions into one executable Wingstaff plan. Identify optional work explicitly. Stop at Wingstaff's digest-bound human approval gate.
- `implement`: execute only the approved construction slice in the assigned Wingstaff worktree. Keep changes incremental and update tests with behavior.
- `verify`: run the real project commands and submit their exact evidence through Wingstaff. Never infer success from code inspection.
- `review`: assess the captured immutable diff against requirements, design, security, and verification evidence.
- `deliver`: report the reviewed changed-path manifest and evidence. Do not commit or push without separate authorization.

## Adaptation rules

1. Preserve AI-DLC's intent-first requirements, adaptive depth, explicit design decisions, unit-oriented construction, and build/test evidence.
2. Represent AI-DLC's Inception across `define` and `plan`; represent Construction across `implement`, `verify`, and `review`; map release-readiness reporting to `deliver`.
3. Operations in stable v1.0.1 is a placeholder. Do not invent deployment automation or a second runtime.
4. Use Wingstaff artifacts and lifecycle tools rather than creating `aidlc-state.md`, `audit.md`, an independent approval ledger, or a nested orchestration loop.
5. Treat upstream rule-detail files as source methodology, not executable Hermes skills. This adapter is the packaged Hermes skill.
6. Stop on missing inputs, invalid artifacts, failed verification, or changed plans. Never fabricate fallback output.

## Provenance

This adapter is derived from the AI-DLC v1.0.1 rules release at commit `e49341dbeb8af82758dd85e96ed7fe9bcf38a447`. The upstream project is licensed under MIT No Attribution; see `references/LICENSE-AIDLC.txt`.
