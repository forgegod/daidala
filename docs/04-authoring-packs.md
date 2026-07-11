# 04 — Authoring workflow packs

Schema-v1 packs are bundled adapters: they map external skill names onto
Wingstaff's fixed lifecycle without changing Python for a particular skill set.
They provide deterministic installation plans and workflow mappings without
adding pack-specific engine branches.

## Before authoring

Confirm that the adapter can use the implemented six-stage order, one
pre-implementation gate, one pinned GitHub source revision, and complete skill
directory digests. Do not encode different mechanics in magic names or
pack-specific branches.

The engine maps every stage row to one Kanban card. Pack skills are pinned to
that card alongside the bundled worker contract; parent links, profile
assignment, blocking, structured handoffs, and worktree ownership stay generic.
Do not encode card lifecycle mechanics inside a pack.

## Add a pack

1. Choose a lowercase, filename-safe pack slug.
2. Create `wingstaff/packs/<slug>.yaml` using the exact schema in the
   [pack reference](03-pack-reference.md).
3. Set `source` to the authoritative HTTPS GitHub publisher/repository URL and
   pin `source_revision` to a full 40-character commit.
4. Declare the bounded supported Hermes range when the pack relies on a
   version-specific host capability.
5. Map at least one skill into every required stage and declare exactly one
   provider: `install` for an external Hermes skill or `bundled` for a
   plugin-packaged adapter.
6. Declare `activation: required` when pack policy always requires the skill in
   that stage; otherwise declare `activation: conditional`. Do not omit the field
   or mark every skill required merely to avoid worker judgment.
7. For external skills, use install targets under the same
   publisher/repository. The final segment must exactly match `name`.
8. Hash every complete external skill directory into `content_digest`, including
   linked scripts and references rather than only `SKILL.md`. Bundled skills
   must omit the digest and carry any required attribution beside the skill.
9. Keep `human_gate_after: plan` unless a different declared stage still occurs
   before `implement` and accurately represents the adapter.
10. Add tests that load the real package resource and assert its lifecycle, gate,
   exact activation mapping, and representative skill mappings.
11. Add a wheel-content assertion when package installation tests exist; the
   package-data rule already includes `wingstaff/packs/*.yaml`.
12. Run the verification commands below.

## Keep the engine pack-neutral

Put these in YAML:

- upstream source identity;
- source revision and Hermes compatibility range;
- per-skill complete-directory digests;
- external-versus-bundled skill provider selection;
- required-versus-conditional activation policy;
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

Passing schema-v1 validation proves internal shape and pin syntax only. It does
not prove that:

- the upstream repository or skill path exists;
- the install target is accepted by the live Hermes CLI;
- the resolved upstream `HEAD` still equals the pinned revision;
- all required skills are installed in a profile;
- the mapped skills produce compatible artifacts.

Do not present validation as installation or readiness. Use `packs install` for
the dry-run mutation plan and `packs check` for installed-name, source,
compatibility, and content verification.

## Fixture requirements

A new bundled pack should have tests for:

- successful loading by slug from package resources;
- the exact six-stage lifecycle;
- a gate before implementation;
- at least one representative mapping from each stage;
- any new generic schema invariant, with both accepted and rejected examples;
- explicit activation on every skill, including rejection of missing or unknown
  modes and a maximum of 32 skills per stage;
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
- Adapter examples: `wingstaff/packs/addyosmani.yaml`, `wingstaff/packs/aidlc.yaml`
- Existing tests: `tests/test_packs.py`
