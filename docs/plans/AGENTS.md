# docs/plans/

## Purpose

Preserve historical plans, shared plan-family contracts, and their
repository-tracked UX design sources and review renders.

## Ownership

- `Pnnnn-<slug>.md` files are immutable historical implementation records.
- `*-execution-contract.md` files preserve shared invariants used by the
  historical plan families; they carry no current execution state or approval
  authority.
- `hermes-dashboard-ux-live.pen` is the historical editable Daidala dashboard
  wireframe source.
- `dashboard-ux-*.png` files are historical review renders exported from that
  source, including workflow inventory/detail and attended lifecycle decision
  states, collapsed/expanded start, Artifacts, and each Config subtab state
  (Constraints covers source selection, template-to-draft creation, and
  maintenance of existing workflow constraint revisions).
- Date-prefixed plans and JSON scope/evaluation records remain historical or
  bounded planning material.

## Local Contracts

### Historical integrity

- Do not create new plan files or change recorded plan IDs, slots, dependencies,
  phase status, checkpoints, findings, evidence, or links to represent new work.
- Preserve historical provenance in place. Correct broken references only through
  an explicitly scoped CHG that records why the historical repair is necessary.
- Use `docs/product/capabilities/` for current observable behavior and
  `docs/changes/active/` for future material implementation progress.

### Historical dashboard wireframe composition

These rules document the accepted legacy Pen source and renders. Current
capability wireframes live under `docs/product/wireframes/`. Every historical
full-page Daidala wireframe follows one invariant composition:

1. **Hermes workspace shell** — preserve the profile-scope banner, full Hermes sidebar, active profile, complete global navigation, Plugins group with Daidala selected, system status, version, geometry, and host theme treatment.
2. **Daidala navigation** — preserve the three primary views in workflow-result order: Workflows, Artifacts, Config. Exactly one is active and it matches the use case.
3. **Use-case workspace** — replace only the page-content subtree for the current workflow, configuration, start, artifact, review, revision, or confirmation task.

Additional UI contracts:

- Workflows is the default view and complete lifecycle inventory. Its first section lists only workflows awaiting attended action; the page header exposes the primary `Start workflow` action. Its compact finished section is named **Recently finished workflows** and shows the latest five terminal workflows matching the current filters, ordered by terminal timestamp descending with stable workflow-ID tie-breaking. Completed, failed, and cancelled workflow outcomes remain distinct from ledger-bound artifacts.
- Each awaiting-action row shows one source-bound sentence describing the next operator action. That sentence is orientation copy, not evidence or approval authority, and opens the matching workflow detail workspace.
- Start, review, revision, approval, cancellation, and other workflow actions open as Workflows subviews, not primary tabs or standalone shells.
- Workflows subviews keep Workflows selected, omit the redundant `Daidala / Workflows` breadcrumb, and provide an explicit `← Back to Workflows` control followed by the exact workflow ID when one exists.
- Workflow detail subviews carry the expanded workflow identity, stage state, artifacts/evidence, consequence preview, and authority controls formerly associated with a separate attention view.
- Start from the closest accepted complete frame. Copy its shell and navigation; do not reconstruct or abbreviate them.
- Breadcrumbs, workflow identity, evidence, forms, previews, confirmation, and actions belong inside the use-case workspace.
- Evidence precedes authority controls. A summary never substitutes for exact evidence; preview is visibly non-mutating; apply requires literal confirmation.
- Show **What the next card receives** only when an operation dispatches a successor card. Its deterministic identities are read-only; normalized operator feedback appears inside the packet before apply. Operations without a successor card use an operation-specific mutation preview and must not fabricate a handoff.
- Banner profile, shell profile selector, mounted controller profile, worker-profile
  assignments, workflow identity, revisions, digests, evidence references, action
  labels, and consequences must agree within one frame. A Daidala form never
  implies that a worker selector or browser-local control can switch the mounted
  controller profile.
- Use Hermes dashboard tokens and patterns: square structural tabs, cream selected/primary controls, bordered secondary controls, amber attention/confirmation, green verified/non-mutating states, and host-radius content cards. Do not introduce a second palette, sidebar, profile selector, or navigation model.
- Config subtabs are Packs, Checkouts/TTL, GitHub Projects, Constraints, and
  Verification. Start workflow selects only inventory-backed ready packs,
  registered repositories, existing worker profiles, and existing Kanban boards;
  contextual links open Config → Packs, board creation/full Kanban management, or
  Hermes Cron rather than adding duplicate management surfaces.
- Start workflow renders the mounted controller profile read-only and may offer a
  worker-profile default only as a convenience that fills all six explicit stage
  assignments. Repository access is shown as server-owned capability readiness,
  never as credential names/values. Browser-local defaults are non-authoritative,
  exclude task/constraint/credential/path data, and must be revalidated before
  Preview or Start. Cron pause stops future admissions only; no screen may depict
  an in-flight timed pause.

## Work Guidance

- Consult only the historical plan needed for provenance; do not load the archive
  as current requirements.
- Do not edit plans or legacy design assets during normal feature work.
- If an explicitly approved provenance repair touches the `.pen` source, load
  `creative/pen-dev`, preserve the established composition, regenerate the
  matching PNG, and verify it before closeout.
- Keep current screen references and generated HTML/PNG pairs under
  `docs/product/wireframes/`.

## Verification

For explicitly approved historical plan or cross-reference repairs:

```bash
python scripts/check_md_links.py .
git diff --check
```

For dashboard wireframe changes, fresh-load the saved `.pen` source and require every affected frame to report no layout problems before export:

```text
snapshot_layout({ parentId: "<frame-id>", maxDepth: 8, problemsOnly: true })
export_nodes({ nodeIds: ["<frame-id>"], outputDir: "<isolated-output-dir>", format: "png", scale: 1 })
```

Then verify:

- the canonical PNG matches the fresh export;
- the complete Hermes shell is present;
- all three Daidala tabs are present in canonical workflow-result order;
- exactly one tab is active and matches the use case;
- only the use-case workspace differs from the accepted source frame;
- no content is clipped or overlapping;
- authority actions retain exact evidence, preview, and confirmation.

## Child DOX Index

*(empty — this is a flat planning and design-source boundary.)*

See [`/AGENTS.md`](../../AGENTS.md) and [`docs/AGENTS.md`](../AGENTS.md).
