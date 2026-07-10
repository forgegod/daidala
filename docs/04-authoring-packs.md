# 04 — Authoring workflow packs

Schema-v1 packs are bundled adapters: they map external skill names onto
Wingstaff's fixed lifecycle without changing Python for a particular skill set.
They do not install skills or execute workflows.

## Before authoring

Confirm that the new adapter can use the implemented six-stage order and one
pre-implementation gate. If it requires different stage mechanics, artifacts,
revisions, or transitions, schema v1 cannot represent it. Do not encode those
requirements in magic names or pack-specific branches.

## Add a pack

1. Choose a lowercase, filename-safe pack slug.
2. Create `wingstaff/packs/<slug>.yaml` using the exact schema in the
   [pack reference](03-pack-reference.md).
3. Set `source` to the authoritative upstream repository.
4. Map at least one external skill into every required stage.
5. Use fully qualified install targets. The final segment must exactly match the
   declared skill `name`.
6. Keep `human_gate_after: plan` unless a different declared stage still occurs
   before `implement` and accurately represents the adapter.
7. Add tests that load the real package resource and assert its lifecycle, gate,
   and representative skill mappings.
8. Add a wheel-content assertion when package installation tests exist; the
   package-data rule already includes `wingstaff/packs/*.yaml`.
9. Run the verification commands below.

## Keep the engine pack-neutral

Put these in YAML:

- upstream source identity;
- stage-to-skill mappings;
- pack-specific skill names and install targets.

Put these in Python only when they are generic schema mechanics:

- structural validation;
- lifecycle and gate invariants;
- immutable runtime types;
- errors shared by every pack.

Do not write code such as `if pack.name == "..."`. If two packs need a new
shared capability, specify it as a versioned schema field, validate it for every
pack, update the runtime dataclass, and add positive and negative tests before
using it.

## Validation limits

Passing schema-v1 validation proves internal shape only. It does not prove that:

- the upstream repository or skill path exists;
- the install target is accepted by the live Hermes CLI;
- the upstream content is trusted or pinned;
- all required skills are installed in a profile;
- the mapped skills produce compatible artifacts.

Do not present a successful pack validation as dependency installation or
workflow readiness. Mechanical skill resolution and revision pinning belong to
Phase 6.

## Fixture requirements

A new bundled pack should have tests for:

- successful loading by slug from package resources;
- the exact six-stage lifecycle;
- a gate before implementation;
- at least one representative mapping from each stage;
- any new generic schema invariant, with both accepted and rejected examples;
- packaged resource presence once wheel inspection is available.

Keep malformed inline dictionaries for validator edge cases; use real YAML
resources for adapter contract tests.

## Verification

From an editable development install, run:

```bash
pytest
ruff check .
wingstaff packs validate <slug>
python -m build
python -m twine check dist/*
```

The repository Markdown contract is checked separately:

```bash
python scripts/check_md_links.py .
```

## Source of truth

- Schema and validator: `wingstaff/packs.py`
- Package-data inclusion: `pyproject.toml`
- Existing adapter example: `wingstaff/packs/addyosmani.yaml`
- Existing tests: `tests/test_packs.py`
