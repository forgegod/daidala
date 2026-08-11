---
name: application-records
description: Use when a material change needs canonical CAP, CHG, decision records, and CAP-linked wireframes for primary human-facing surfaces.
version: 1.3.0
author: Hermes contributors
license: MIT
metadata:
  hermes:
    tags: [product, capability, change-records, documentation]
    related_skills: [capability-wireframes]
---

# Application Records

## Overview

Keep three distinct truths: an external request explains why work is wanted; a
capability record (CAP) describes shipped behaviour; and an active change record
(CHG) tracks implementation progress. Code and executable tests remain the final
proof of behaviour.

This skill defines the portable canonical layout:

- `docs/product/capabilities/CAP-*.md` for current behaviour;
- `docs/changes/active/CHG-*.md` for active progress; and
- `docs/changes/archive/CHG-*.md` for completed implementation receipts.

Projects adopting this skill use these names and paths. Their contributor
instructions supply product-specific policy, tests, and validation commands.

## When to Use

- A request adds, removes, fixes, or changes material user-visible behaviour.
- A permission, privacy, data-handling, or operator-visible outcome changes.
- An agent needs to create, resume, split, complete, or archive a CHG record.
- A durable choice must be classified as capability-local or cross-cutting.

Do not use for a refactor, formatting change, dependency update, or internal
hardening that preserves observable behaviour. Do not use a CAP or CHG to
replace architecture, privacy, security, or deployment documentation.

## Authoritative Surfaces

Read these before changing a record:

| Need | Read |
| --- | --- |
| Repository-wide obligations | The target repository's root contributor instructions and applicable child contracts. |
| Current capability contract | `docs/product/README.md` and affected `docs/product/capabilities/CAP-*.md`. |
| Change-progress lifecycle | `docs/changes/README.md` and affected `docs/changes/{active,archive}/CHG-*.md`. |
| Durable cross-cutting decision | `docs/architecture.md`, `docs/privacy.md`, `docs/design-decisions.md`, and equivalent local contracts. |

## Procedure

1. **Classify the request.**
   - If it is vague or blocked by unresolved decisions, use Wayfinder only to
     resolve the decision frontier. The tracker map remains discovery material.
   - If it changes material behaviour, identify affected CAP IDs and create or
     resume one CHG record before implementation.
   - If it preserves observable behaviour, state that no CAP/CHG change is
     needed and proceed under the applicable implementation contract.

2. **Create or resume the CHG authority.**
   - Follow `docs/changes/README.md`'s canonical shape and lifecycle.
   - Link the external ticket or write `Direct operator request: <verbatim request>`
     when no ticket exists. Never invent a ticket ID.
   - Set one phase to `in-progress`; include executable verification gates.
   - For material work, the tracked CHG is the execution plan. Do not create a
     competing private plan carrying the same progress.
   - For a pending proposal with a primary human-facing surface, keep visual
     review artifacts under the CHG. Do not allocate a future CAP ID or add the
     proposal to the product wireframe manifest: those surfaces describe current
     implementation only.

3. **Make current behaviour explicit.**
   - Add or amend the affected CAP in the same vertical slice as implementation
     and behaviour tests.
   - State only present-tense, falsifiable outcomes. Link architecture and
     privacy/security contracts instead of copying their rules.
   - If code/tests contradict the CAP, fix the code or CAP before
     completion; do not leave an ambiguous claim.
   - When the capability adds or changes a primary human-facing surface, load
     `capability-wireframes`. At implementation, create the CAP-linked static
     HTML/PNG pair, manifest entry, and index link in the same vertical slice as
     the runtime surface and behavior tests. The wireframe illustrates the
     interface but does not replace behavior-test evidence.

4. **Place decisions correctly.**
   - Record a capability-local rule in its CAP only when it changes how the
     implemented behaviour must be understood.
   - Record irreversible or cross-cutting runtime, authentication,
     authorization, persistence, privacy, or observability choices in
     `docs/design-decisions.md` and update the live contracts in the same change.
   - Leave short-lived implementation reasoning in the CHG or Git history.

5. **Prove and record progress.**
   - Run the current phase gate. Mark it done only after it passes.
   - Run the project's `records:check` integration plus affected tests and the
     required workspace/release gate for cross-boundary work.
   - Update the CHG before the implementation commit so a new session can resume
     from repository truth.

6. **Close the change.**
   - Confirm affected CAPs describe merged behaviour and link executable tests.
   - Run the project's full integration gate.
   - Set the CHG done, move it from `active/` to `archive/`, and retain it as an
     implementation receipt, not a feature specification.

## Common Pitfalls

1. **Tracker-shaped truth.** A ticket marked complete is not proof of merged or
   deployed behaviour. Link it from a CHG; do not copy its status into a CAP.
2. **Plan-shaped truth.** A completed phase table explains work history. It does
   not describe current behaviour; the CAP must carry that outcome.
3. **CAP churn.** Do not update a CAP because implementation details changed.
   Update it only when a material outcome changed.
4. **Unproved claims.** A CAP without behaviour-test evidence is a coverage
   gap, not an implemented proof. Add focused coverage or state the bounded
   gap precisely before calling the record complete.
5. **Decision inflation.** Do not create a decision record for local naming or
   code-layout choices. Reserve it for durable cross-cutting forks.
6. **Premature promotion.** Do not move a CHG review screenshot, Pencil file,
   or planned screen into `docs/product/wireframes/`. Regenerate a CAP-linked
   HTML/PNG pair only when its product surface and evidence exist.

## Verification Checklist

- [ ] Every material changed behaviour has an affected CAP and behaviour-test evidence.
- [ ] Every qualifying primary human-facing surface has a current CAP-linked
      HTML and PNG wireframe.
- [ ] Pending CHG review artifacts are not listed in the product wireframe
      manifest and do not claim unimplemented CAP IDs.
- [ ] Every active material request has exactly one CHG progress authority.
- [ ] Every CHG references its source request and valid CAP IDs.
- [ ] The project's `records:check` integration exits 0.
- [ ] The active phase gate and required workspace checks pass.
- [ ] Completed CHGs are in `archive/`; active CHGs are not marked done.
