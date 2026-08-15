# CHG-0013: Complete pack installation and Packs UI overhaul

**Status:** done
**Source request:** Direct operator request: "create a plan with phased-plan-design skill for the pack installation change as recommended for the correct implementation; the ui need then a overhaul change so create the phased plan first"
**Affected capabilities:** CAP-0003, CAP-0007
**Created:** 2026-08-14

## Outcome

Daidala will separate a workflow pack's complete installable skill catalog from
its stage-activation mapping, install the complete Addyosmani catalog through one
preview-confirmed pack operation, and present pack identity, installation scope,
lifecycle use, readiness, warnings, and remediation in a redesigned Config →
Packs surface.

## Scope

### Current evidence and problem boundary

- The current schema stores provider, digest, and activation metadata together in
  each `stages[].skills[]` entry. `required_skills()` therefore treats only
  stage-mapped skills as install requirements and cannot represent an install-only
  pack member without assigning it to a lifecycle stage.
- The Addyosmani adapter currently maps 20 skills into six lifecycle stages. A
  repository-wide reference analysis found 57 directed cross-skill references
  across 14 of 24 skills; the selected 20 reach all four omitted skills:
  `api-and-interface-design`, `context-engineering`,
  `frontend-ui-engineering`, and `using-agent-skills`.
- The self-contained fork branch is published at immutable commit
  [`9055b8a18d866b290301a131970fcf2805a7a69c`](https://github.com/forgegod/addyosmani-agent-skills/commit/9055b8a18d866b290301a131970fcf2805a7a69c).
  A corrected isolated Hermes 0.20.0 probe installed 15 raw-revision skill
  targets and blocked nine: seven with a dangerous verdict and two with a
  caution verdict. Hermes returns exit code zero for these blocked installs, so
  the earlier exit-code-only 24-success claim was invalid.
- Config → Packs currently derives its skill inventory and its **Install all**
  action from stage entries. It presents individual installation and availability
  controls inside lifecycle groups, but it cannot explain the difference between
  complete pack membership and direct stage activation.

### Pack model

- Replace pack schema version 1 with one explicit version 2 shape; do not add a
  compatibility parser. Migrate both bundled packs in the same phase so the
  engine has one contract:
  - top-level `skills` owns each unique skill's provider and expected content
    digest;
  - `stages[].skills[]` owns only the catalog name and stage-specific activation
    mode;
  - every stage reference must resolve to exactly one catalog entry;
  - provider identity remains exclusive: immutable external install target or
    plugin-bundled skill, never both.
- Define separate immutable runtime types for catalog skills and stage bindings.
  Keep lifecycle decisions pack-owned and the engine pack-neutral.
- Make installation, readiness, content lookup, source projection, and pack-wide
  enable/disable operate over the complete catalog. Make worker/card activation
  operate only over stage bindings.
- Populate the Addyosmani catalog with all 24 skills from the scanner-clean commit
  `bf223959faae96825f78ddf7bc33e114f3303c1e` and
  retain the current 20 stage mappings unless interaction/design review finds a
  methodology reason to change one. A catalog skill without a direct stage
  binding is labeled **catalog-only**, not silently assigned to a stage.
- Migrate AI-DLC to the same catalog/stage split without changing its lifecycle
  behavior. Reject duplicate catalog names, unknown stage names, mutable external
  targets, incomplete digests, and conflicting providers.
- Recompute every expected digest from the exact bundle installed by Hermes, then
  update the committed Daidala project pack revision and pack-content digest.

### Installation contract

- Preserve the Hermes-only boundary. One Daidala pack apply remains one logical
  operator action while the service emits one deterministic
  `hermes skills install <immutable-raw-url>` command per missing external catalog
  skill. Do not use `npx`, a tap, recursive repository installation, direct file
  copying, or a skill bundle as an installer.
- Make pack installation the only installation mutation exposed by Config →
  Packs. Retain individual and pack-wide enable/disable controls because enabled
  state is separate from installed content. Do not silently enable a skill that
  the active profile disabled.
- Preview must bind pack identity, immutable source revision, complete catalog,
  missing set, current readiness identity, and ordered install actions. Apply
  requires literal confirmation and the exact fresh preview digest.
- A partial external failure remains explicit. Successful preceding Hermes
  installs are not disguised as an atomic rollback; the fresh next preview offers
  **Retry missing skills** for only the remaining catalog entries.
- Pack readiness requires every catalog skill to be available and enabled. Stage
  activation manifests continue to contain only the skills bound to that stage.
- Preserve warning-only digest semantics: mismatches stay visible and do not turn
  a successful install into failure or block workflow start. Missing or disabled
  catalog entries remain blockers.
- Hermes 0.20.0 refuses nine skills at commit `9055b8a...` unless installation
  uses `--force`. Daidala does not bypass Hermes scanner verdicts implicitly.
  The operator selected a new scanner-clean immutable revision; runtime pack
  changes remain gated until all 24 skills appear in a fresh Hermes inventory.

### Config → Packs interaction model

The visual design phase must resolve this operator flow before runtime code changes:

1. A compact pack selector identifies the selected bundled pack and its readiness.
2. A pack summary names its source revision, Hermes range, lifecycle stages,
   catalog coverage, installed count, enabled count, digest-warning count, and
   direct stage-binding count.
3. One dominant action reads **Install pack**, **Retry missing skills**, or
   **Pack installed** from current state. Installation opens a bounded preview
   and literal-confirmation panel naming the selected pack, source revision,
   total catalog size, missing count, and shared-install side effect.
4. A lifecycle section shows stage bindings and required/conditional activation
   without pretending that stage membership is installation ownership.
5. A searchable skill inventory lists all catalog members with stage chips or a
   **Catalog-only** label, installed/enabled/readiness state, digest warning, and
   source detail. Selecting a row focuses one detail panel; it does not expose an
   individual install mutation.
6. Individual and pack-wide enable/disable previews state that installed skill
   content is shared while enabled state belongs to the active Hermes profile.
7. The design covers loading, no-selection, unavailable check, fresh ready,
   missing, partially installed, disabled, digest-warning, failed action, stale
   preview, confirmation, narrow viewport, keyboard focus, and retry states.

### Documentation and ownership

- Amend [CAP-0003](../../product/capabilities/CAP-0003-operator-dashboard.md)
  and its matching generated wireframe only when the Packs UI behavior is
  implemented. Pending review artifacts stay under a CHG-local directory and do
  not consume a new CAP ID.
- Update the pack reference, skill-usage guidance, CLI/dashboard operator docs,
  owning DOX contracts, package fixtures, and release-content expectations in the
  phase that changes their live contract.
- Preserve `docs/plans/` unchanged as historical provenance.

### Explicit exclusions

- No arbitrary external pack upload, pack authoring UI, repository tap, installer
  fallback, uninstall/delete action, runtime network discovery of skill names, or
  automatic parsing of prose cross-references.
- No loading all 24 skills into every worker context. Hermes progressive
  disclosure and stage activation remain distinct from installation completeness.
- No source-repository merge is required; Daidala pins the exact published commit.
- No implementation phase starts from this plan alone. The two approval gates
  below are mandatory.

## Phases

| Phase | Status | Verification gate |
| --- | --- | --- |
| Plan approval | done | The operator approved CHG-0013 on 2026-08-14, authorizing only the review-only interaction-design phase. Records and Markdown links passed before approval. |
| Interaction design and visual approval | done | Seven CHG-local native review artifacts cover normal, partial, warning, failure, confirmation, narrow, and progressive-detail states; interaction audit, rendering, records, and links passed; direct operator approval was recorded on 2026-08-14. |
| Pack schema and complete-installation vertical slice | done | Scanner-clean revision `bf223959faae96825f78ddf7bc33e114f3303c1e` is remotely verified; a fresh Hermes home records 24 installed directories, 24 CLI inventory entries, 24 install receipts, and zero blocked receipts; schema-v2 parser/model tests, both bundled-pack migrations, the immutable 24-skill catalog, install/content/readiness regressions, CLI tests, full pytest, Ruff, both pack validations, records, and Markdown links pass. |
| Packs UI vertical slice | done | Backend projections, authenticated routes, browser rendering, focus/keyboard behavior, confirmation/stale/error states, CAP-0003/CAP-0007 text and wireframes, dashboard API/assets/browser probes, responsive screenshot review, and focused Ruff/tests pass. |
| Integration and closeout | done | `python scripts/check_records.py .`, `lefthook validate`, `pytest`, `ruff check .`, both pack validations, package build, Twine, release-content audit, Markdown links, isolated real-Hermes pack installation, DOX pass, and direct operator acceptance passed before archival. |

## Decisions

- The active CHG is the tracked phased plan; no competing file is created under
  `docs/plans/`.
- The complete skill catalog and stage activation mapping are separate first-class
  concepts. Adding omitted skills to arbitrary lifecycle stages is rejected.
- Schema version 2 is a clean replacement, not an optional version-1 extension.
  Both bundled adapters migrate together.
- **Install pack** is one reviewed Daidala action composed of native Hermes
  per-skill installs. UI simplicity does not justify bypassing Hermes or pretending
  the host provides atomic bulk installation.
- The UI is pack-first rather than a grid of unrelated skill mutations. Skill
  details remain inspectable; installation authority remains pack-wide.
- Shared installed content, profile-local enabled state, stage activation, and
  digest integrity are separate status dimensions and must not share one ambiguous
  badge or count.
- Digest mismatches retain the established explicit-warning, non-blocking contract.
- Scanner verdicts are not bypassed. The operator selected a new scanner-clean
  immutable fork revision rather than an explicit `--force` installation policy.
- Visual approval precedes runtime UI work. The static product wireframe is
  updated only in the implementation slice, after the review artifact is accepted.

## Evidence

- 2026-08-14: committed and pushed the self-contained fork branch as
  `9055b8a18d866b290301a131970fcf2805a7a69c`; remote branch identity matched.
- 2026-08-14: a corrected isolated Hermes 0.20.0 home installed 15 immutable raw
  skill targets and blocked nine. The audit receipt records seven dangerous and
  two caution verdicts. The previous 24/24 claim counted zero exit codes and did
  not verify the installed inventory.
- 2026-08-14: direct operator decision — "Create and pin a new scanner-clean fork
  revision (recommended)". A force-install policy is not authorized.
- 2026-08-14: committed and pushed scanner-clean fork revision
  `bf223959faae96825f78ddf7bc33e114f3303c1e`; the remote branch resolved to the
  same immutable commit.
- 2026-08-14: a fresh isolated Hermes 0.20.0 home installed all 24 immutable raw
  targets. Installed directories, `hermes skills list`, and audit receipts each
  contained all 24 exact names; the audit contained zero blocked receipts. The
  digests of those Hermes-installed directories are the catalog identities in
  `daidala/packs/addyosmani.yaml`.
- 2026-08-14: direct operator approval — "Approve CHG-0013 and begin the
  review-only interaction-design phase (recommended)". This authorizes design
  artifacts only; runtime, schema, and pack-pin edits remain gated.
- 2026-08-14: the CHG-local review package contains seven native renders covering
  ready, partial, warning, failure, confirmation, narrow, and progressive-detail
  states. Pencil reported no layout problems for all seven roots; interaction and
  visual audits found no remaining design defect.
- 2026-08-14: direct operator visual approval — "approved visual
  recommendations". The exact audited Pen source is preserved with the review
  exports; pack-schema and repin work may proceed.
- 2026-08-14: schema version 2 now separates `CatalogSkill` providers from
  `StageSkill` activation bindings. Both bundled packs, the project-manifest
  resource digests, catalog-wide installation/content/readiness, worker-card
  resolution, plugin projections, and regression fixtures use the new shape.
- 2026-08-14: full pytest, repository-wide Ruff, both pack validations, record
  validation, Markdown links, and diff whitespace passed. [CAP-0007](../../product/capabilities/CAP-0007-complete-workflow-pack-installation.md)
  records the implemented installation capability; CAP-0003 remains unchanged
  until the Packs UI slice is implemented.
- [CHG-0012](../archive/CHG-0012-pin-hermes-pack-skill-installation.md)
  remains the receipt for the prior immutable single-skill installation boundary;
  this CHG supersedes its 20-stage-entry inventory shape without rewriting history.
- 2026-08-15: Config → Packs now renders a catalog-first pack workspace with one
  complete-pack install/retry action, lifecycle binding summary, searchable
  inventory, catalog-only labels, progressive narrow disclosure, literal skill
  detail drawer, digest warnings, and profile-local enable/disable confirmation.
- 2026-08-15: isolated Hermes dashboard browser verification exercised readiness
  refresh, install preview, skill search/detail, profile-local action preview,
  Escape focus restoration, and a 390-pixel viewport with four initial rows and
  explicit 24-row disclosure. Focused dashboard/API/service tests and Ruff pass;
  they additionally prove stale-preview rejection, individual-install refusal,
  structured partial-failure receipts, and fresh missing-only retries.
- 2026-08-15: CAP-0003 and CAP-0007, dashboard/test DOX ownership, and their
  generated 1440 × 960 product wireframes describe the implemented overview and
  shared-install confirmation. Record validation reports seven capabilities,
  fifteen change records, and five wireframes; Markdown links, generator syntax,
  and both visual export reviews pass.
- 2026-08-15: closeout review corrected post-install failure reconciliation,
  dialog focus containment/restoration, nested drawer dialogs, duplicate row
  actions, and responsive disclosure counts. The full pytest suite, repository-wide
  Ruff, Lefthook, both pack validations, package build, Twine, release-content
  audit, records, links, JavaScript syntax, and whitespace checks pass. A final
  fresh Hermes home also converged all 24 native installs with no remaining action
  or blocker.
- 2026-08-15: direct operator approval — "Approve closeout: archive CHG-0013 and
  create the semantic commit (recommended)". This accepts the verified Packs UI
  vertical slice and authorizes its closeout commit without a push.
