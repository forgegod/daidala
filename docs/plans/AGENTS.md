# docs/plans/

## Purpose

Own executable plans, shared plan-family contracts, and repository-tracked UX design sources and review renders.

## Ownership

- `Pnnnn-<slug>.md` files are active executable plans.
- `*-execution-contract.md` files own shared invariants consumed by multiple active plans; they carry no execution state or approval authority.
- `hermes-dashboard-ux-live.pen` is the editable Daidala dashboard wireframe source.
- `dashboard-ux-*.png` files are canonical review renders exported from that
  source, including workflow inventory/detail and attended lifecycle decision
  states, collapsed/expanded start, Artifacts, and each Config subtab state
  (Constraints covers source selection, template-to-draft creation, and
  maintenance of existing workflow constraint revisions).
- Date-prefixed plans and JSON scope/evaluation records remain historical or bounded planning material; active execution must identify its exact source explicitly.

## Local Contracts

### Plan structure

- Plans name exact files, verification gates, stop conditions, and unresolved decisions.
- Active executable plans use `Pnnnn-<slug>.md` with matching `Plan ID`, `Execution slot`, `Created`, `Depends on`, and `Status` headers. Creation dates are provenance only; dependency-ready plans execute by ascending slot.
- Reordering changes the slot prefix and header together and updates inbound links. Split plans use distinct stable IDs and explicit dependencies so moved phases appear in exactly one active file.
- Active plans normally carry one to three context-local phases and name exact `Context sources`, an `Entry checkpoint`, and a concrete `Produces` checkpoint. A fresh session reads only those sources and direct-dependency evidence, not completed predecessor plans in full.
- Plans above 500 lines or 40 KiB require a split or an explicit atomicity rationale. Shared execution contracts may own pinned family invariants, but have no execution slot, status table, findings ledger, or approval authority.
- Repository-tracked content references only repository-tracked plans. Never depend on profile-private plans, `/tmp`, or another ephemeral location.
- During phase execution, adopt actionable findings into the tracked active plan before changing implementation scope. Do not persist plan fragments, findings, evidence notes, or diff snapshots in temporary directories.
- Describe the current intended design without iteration diaries or stale migration breadcrumbs.

### Dashboard wireframe composition

Every full-page Daidala wireframe follows one invariant composition:

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

- Before editing a plan, read only its declared context sources and applicable parent contracts; do not load the whole planning archive by default.
- Update the active plan before implementation proceeds when a design decision or actionable finding changes scope, ordering, dependencies, or verification.
- Before editing a `.pen` source, load the `creative/pen-dev` skill and inspect the current Pen schema.
- For a new wireframe use case, copy an accepted complete screen and replace only its `Page content` subtree. Change the active Daidala tab only when the use-case map requires it.
- Preserve the `.pen` source as canonical. Regenerate the matching PNG from a fresh headless Pen load; do not treat a screenshot cache as approval evidence.
- Promote accepted timestamped review iterations to stable repository filenames and copy the canonical render beside the source as the final task step; timestamps are cache-workaround metadata only. Verify both files, then open the canonical render for user review before closeout.
- Keep implementation behavior in active plans and shared contracts. Keep visual composition rules here and detailed screen behavior in `P0250-daidala-dashboard-ux-concept.md`.

## Verification

For plan and cross-reference changes:

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
