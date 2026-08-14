# Packs UI review artifacts

These files are approved review-only interaction-design evidence for CHG-0013.
They do not define current product behavior and remain CHG-local until runtime
implementation supplies matching behavior evidence and a CAP-linked wireframe.

## Review images

- [Ready](exports/packs-ready.png): all 24 catalog skills are installed and
  enabled; workflows still activate only their stage-bound skills.
- [Partial installation](exports/packs-partial-installation.png): missing installs
  and a profile-disabled skill have separate remediation.
- [Digest warnings](exports/packs-digest-warnings.png): warning-only mismatches
  remain visible without blocking workflow start.
- [Failed action](exports/packs-failed-action.png): successful installs remain and
  the exact three failures are retryable from their receipt.
- [Install confirmation](exports/packs-install-confirmation.png): the bounded
  preview names the exact revision, 24-skill shared-store effect, unchanged active
  profile, and partial-failure behavior.
- [Narrow partial](exports/packs-narrow-partial.png): the blocked state, missing
  count, and both remediation paths remain usable at 390 × 844.
- [Skill detail](exports/packs-skill-detail.png): progressive disclosure separates
  installed content, profile-local enablement, lifecycle ownership, immutable
  source identity, and digest state.

## Interaction audit

### Entry, selection, and readiness

- `Config → Packs` opens a pack-first workspace. A compact selector names the
  selected pack; no skill card can become the installation owner.
- Loading shows stable selector and summary placeholders, an announced loading
  status, and no enabled mutation.
- No selection asks for a pack selection and exposes no install, enable, disable,
  or retry action.
- An unavailable readiness check preserves the last known counts as stale,
  identifies the failed check, and offers only **Retry validation**.
- Ready, warning, blocked, and failed states use text labels as well as color.

### Installation, confirmation, and retry

- **Install pack** and **Retry missing skills** are pack-level operations backed by
  deterministic native Hermes installs. No inventory row exposes installation.
- Confirmation names the selected pack, immutable revision, shared-store scope,
  catalog size, active-profile non-effect, and non-atomic partial-failure rule.
- A stale preview is rejected before mutation. The dialog stays open, announces
  that pack state changed, refreshes counts and revision evidence, and requires a
  new explicit confirmation.
- Partial results preserve successful installs. Retry addresses only missing or
  receipt-failed skills and never switches source.

### Profile state and skill detail

- Individual and pack-wide enable/disable operations explicitly name the active
  profile. They do not claim to remove shared installed content.
- Missing or disabled catalog skills block readiness. Digest mismatches remain
  explicit warnings and do not block installation or workflow start.
- Search accepts skill name, lifecycle stage, and catalog ownership. Filters expose
  all 24 entries and the four catalog-only entries without changing readiness.
- Selecting a row opens one detail drawer with role, stage or **Catalog-only**
  ownership, installed/enabled state, immutable source, and digest status. It does
  not load the skill into agent context.

### Keyboard, focus, and responsive behavior

- Focus order follows selector, pack action, lifecycle summary, status notice,
  search, filters, inventory rows, and progressive detail actions.
- Opening a confirmation or detail panel moves focus to its heading. `Escape` and
  **Cancel**/**Close** return focus to the invoking control; confirmation traps
  focus while open.
- The narrow layout replaces the desktop table with a truthful `4 of 5 shown`
  subset and keeps missing-install and disabled-profile remediation distinct.

## Verification and approval

- Pencil reported `No layout problems.` for all seven native roots.
- Native PNG exports were visually audited for hierarchy, clipping, glyphs,
  state semantics, confirmation boundaries, and responsive behavior.
- [The editable Pen source](packs-overhaul-review.pen) is the exact source for the
  audited PNG exports.
- Direct operator approval on 2026-08-14 — "approved visual recommendations" —
  accepts this review package. Runtime and product-wireframe changes remain
  separately gated by CHG-0013.
