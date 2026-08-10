---
name: application-records-migration
description: Use when migrating legacy docs and plans into canonical CAP and CHG records.
version: 1.1.0
author: Hermes contributors
license: MIT
metadata:
  hermes:
    tags: [migration, product, capability, change-records, documentation]
    related_skills: []
---

# Project Records Migration

## Overview

Migrate a legacy documentation and planning tree into canonical capability
(CAP) and change-progress (CHG) records without fabricating implementation
status or destroying useful architecture, operational, evaluation, and
historical material. This is audit-first work: classify before moving, and
verify every current-state claim against source and tests.

The migration target is fixed: `docs/product/capabilities/CAP-*.md` describes
current behaviour; `docs/changes/active/CHG-*.md` tracks active work; and
`docs/changes/archive/CHG-*.md` retains completed receipts. The project adds
its own policy, tests, and `records:check` command around that layout.

## When to Use

- A repository has broad numbered documentation plus dated or phased plans.
- A team wants tickets to remain change requests while Git records current
  functionality and active implementation progress.
- A documentation tree has current architecture and operator documents, a
  support-status index, active work plans, dated plans, and retained evaluation
  evidence.

Do not use to rewrite a healthy single capability or to delete an old plan
archive merely because a new record structure exists.

## Preconditions

1. Read the target repository's contributor instructions and applicable child
   contracts.
2. Re-run `git status --short --branch` in the target repository.
3. Read the legacy documentation index, documentation ownership contract,
   active-plan contract, and any current architecture/privacy/runbook contracts.
4. Identify the target repository's existing tests, runtime source, and release
   process. A legacy support-status row is never proof by itself.
5. Create a repository-tracked migration CHG before mutating the legacy tree.

If the target has uncommitted unrelated documentation work, inventory it and
stop rather than sweeping it into the migration.

## Classification Matrix

Build a migration map before editing. Each legacy artifact receives exactly one
primary destination; link rather than duplicate content.

| Legacy artifact | Destination | Rule |
| --- | --- | --- |
| Current user/operator behaviour grounded in source and tests | `docs/product/capabilities/CAP-*.md` | Extract concise falsifiable behaviour and test links; keep deep technical detail in its current architecture/runbook owner. |
| Architecture, privacy, security, setup, or operations contract | Retain current owner | Link from a CAP where it proves a capability; do not copy it into every CAP. |
| Active, dependency-ready phased plan for a material request | `docs/changes/active/CHG-*.md` | Preserve stable scope, external request, impacts, dependencies, phases, and gates. The CHG becomes progress authority. |
| Completed/cancelled plan or dated retrospective | `docs/changes/archive/CHG-*.md`, only when useful as a receipt | Do not bulk-convert every historical plan. Git history remains history. |
| Irreversible cross-cutting decision | Decision record plus live contract | Do not leave the decision only in a plan. |
| Evaluation fixture, result, rendered design, or generated evidence | Retain its evidence owner | It proves a bounded result, not product behaviour or plan progress. |
| Vague request or unresolved design question | Tracker/decision-discovery map | Resolve it before creating a CAP or implementation CHG. |

## Structured legacy migration

For a tree with a documentation support-status table, runtime contracts, active
plans, dated plans, and versioned evaluation results:

1. Treat the support-status table as an inventory only. Verify each claimed
   capability against the named runtime modules and tests.
2. Keep architecture, workflow, security, and runbook documents in place when
   they remain their best detailed owner. Create concise CAPs that link to those
   documents and executable tests.
3. Convert only genuinely active material-change plans into active CHGs.
   Preserve direct dependencies and verification gates. If an old plan
   has no tracker, use the target project's direct-request convention and cite
   the legacy repository-relative path; do not fabricate a ticket.
4. Classify dated plans individually. Most are historical context and should
   remain in Git history or an existing archive, not become live CHGs.
5. Retain evaluation results, fixtures, and generated review artifacts under
   their existing evidence contract. Link them from a CAP or CHG only where they
   directly prove the current claim or phase gate.

## Procedure

1. **Inventory without mutation.** Produce a table with legacy path, current
   claim, source/test evidence, classification, target record, and action. Mark
   every unverified claim as a coverage gap.
2. **Install the target contract.** Add `docs/product/README.md`,
   `docs/product/capabilities/`, `docs/changes/README.md`,
   `docs/changes/{active,archive}/`, templates, contributor routing, a
   `records:check` integration, and a migration CHG. Do not claim the migration
   complete yet.
3. **Migrate the minimum current baseline.** Start with two to four material
   behaviours that have existing tests. Add CAPs and update the product index.
   Leave unverified areas out of the implemented baseline.
4. **Convert active work at verified phase boundaries.** Create CHGs from legacy
   plans; keep original plan IDs as references where useful, but do not leave two
   mutable progress authorities.
5. **Promote durable decisions.** Move only live cross-cutting decisions into
   the target project's decision-record/live-contract pair. Keep routine
   implementation reasoning out of permanent documents.
6. **Reconcile and retire carefully.** Move or delete a legacy document only
   after every durable current claim has a surviving owner, inbound links are
   repaired, and the new CAP/CHG records validate. Prefer retaining a detailed
   architecture or runbook document over flattening it into a CAP.
7. **Verify in layers.** Run `records:check`, a Markdown-link check, targeted
   tests for every migrated CAP, and the workspace gate. Update migration CHG
   evidence only after each gate passes.

## Common Pitfalls

1. **Mass conversion.** A filename pattern cannot distinguish a current contract
   from a historical plan. Classify first.
2. **Status laundering.** Never turn a legacy "implemented" cell into a CAP
   without confirming source and executable evidence.
3. **Duplicate authorities.** Do not retain an old active plan and a new CHG with
   independent phase statuses. Select one progress authority and archive or
   clearly retire the other after links are repaired.
4. **Architecture flattening.** CAPs are concise behaviour indexes, not a place
   to copy whole architecture or runbook chapters.
5. **History deletion.** Git carries historical rationale. Do not delete dated
   plans or evidence merely to make the new structure look tidy.

## Verification Checklist

- [ ] Every legacy artifact appears once in the migration map.
- [ ] Each implemented CAP is grounded in source and an executable test.
- [ ] Active CHGs have one mutable status authority and valid dependencies.
- [ ] Architecture, operational, decision, and evidence documents retain clear owners.
- [ ] Inbound Markdown links resolve after moves.
- [ ] Record checks, targeted tests, and target workspace gates pass.
