# CAP-0007: Complete workflow-pack installation

**Status:** implemented
**Primary surface:** Config → Packs through CAP-0003; CLI adapter

## Outcome

An operator can inspect and install a workflow pack's complete immutable skill catalog through Hermes while lifecycle activation remains limited to the skills bound to each stage.

## Behavior

- Pack schema version 2 declares each unique provider and expected content digest once in a top-level catalog; lifecycle stages bind only catalog names and required or conditional activation.
- The Addyosmani pack pins all 24 skills at one immutable scanner-clean fork revision. Twenty skills are stage-bound; four catalog-only skills remain installable, inspectable, and readiness-controlled without being loaded onto worker cards.
- Pack installation is a dry run by default and expands the missing catalog into deterministic `hermes skills install <immutable-raw-url> --yes` actions. Apply requires explicit confirmation and verifies installed names afterward.
- Pack readiness requires every catalog member to be installed and enabled. Installation preserves existing profile-local disabled state, and content-digest differences remain visible non-blocking warnings.
- Bundled and installed catalog skills expose bounded `SKILL.md` content. Uninstalled external skills expose installation and pinned-source metadata without substituting remote source text.

## Evidence

### Runtime

- [`daidala/packs.py`](../../../daidala/packs.py) — strict schema-v2 catalog and stage-binding model.
- [`daidala/skills.py`](../../../daidala/skills.py) — catalog-wide inventory, immutable Hermes actions, and installed-bundle digest comparison.
- [`daidala/pack_service.py`](../../../daidala/pack_service.py) — shared validation, readiness, content, and preview-confirmed mutation service.
- [`daidala/packs/addyosmani.yaml`](../../../daidala/packs/addyosmani.yaml) — immutable 24-skill catalog and 20-skill lifecycle binding.
- [`dashboard/dist/index.js`](../../../dashboard/dist/index.js) — complete-pack preview, explicit shared-store confirmation, and missing-only retry surface.

### Tests

- [`tests/test_packs.py`](../../../tests/test_packs.py) — strict schema-v2 separation and fail-closed catalog references.
- [`tests/test_skill_installation.py`](../../../tests/test_skill_installation.py) — 24 deterministic Hermes actions and post-apply convergence.
- [`tests/test_pack_service.py`](../../../tests/test_pack_service.py) — catalog-only content, readiness, disabled-state preservation, and action previews.
- [`tests/test_worker_contract.py`](../../../tests/test_worker_contract.py) — stage bindings remain the exact worker-card skill set.
- [`tests/test_dashboard_assets.py`](../../../tests/test_dashboard_assets.py) — pack-only installation, confirmation, receipt, and responsive inventory contracts.

## Contracts

- [Workflow-pack reference](../../03-pack-reference.md)
- [Pack adapters](../../09-pack-adapters.md)
- [Skill usage and user control](../../11-skill-usage-and-user-control.md)

## Links

- [Complete pack installation and Packs UI change](../../changes/archive/CHG-0013-complete-pack-installation-and-packs-ui.md)
- [HTML wireframe](../wireframes/html/CAP-0007-complete-workflow-pack-installation.html)
- [PNG wireframe](../wireframes/exports/CAP-0007-complete-workflow-pack-installation.png)
