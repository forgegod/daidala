# 03 — Workflow-pack reference

This document describes schema version 2 as implemented by
`daidala/packs.py`. The schema is pack-neutral, separates installable catalog
membership from stage activation, and includes pinned external source and
skill-content integrity fields.

## Location and loading

Bundled packs live at `daidala/packs/<name>.yaml` and are loaded with
`importlib.resources`, so package and source-tree access use the same path.
`load_pack(name)` accepts a conservative alphanumeric-and-hyphen slug and
rejects unknown resources.

## Schema version 2

```yaml
schema_version: 2
name: example
source: https://github.com/publisher/repository
source_revision: 0123456789abcdef0123456789abcdef01234567
hermes_version_constraint: ">=0.18.2,<0.21.0"
skills:
  - name: requirements-skill
    install: publisher/repository/skills/requirements-skill
    content_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
  - name: catalog-only-skill
    install: publisher/repository/skills/catalog-only-skill
    content_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
lifecycle:
  human_gate_after: plan
  stages:
    - id: define
      skills:
        - name: requirements-skill
          activation: required
    - id: plan
      skills:
        - name: requirements-skill
          activation: required
    - id: implement
      skills:
        - name: requirements-skill
          activation: conditional
    - id: verify
      skills:
        - name: requirements-skill
          activation: conditional
    - id: review
      skills:
        - name: requirements-skill
          activation: required
    - id: deliver
      skills:
        - name: requirements-skill
          activation: conditional
```

## Field contract

| Path | Type | Implemented requirement |
|---|---|---|
| `schema_version` | integer | Must equal `2`; version 1 is rejected without a compatibility reader. |
| `name` | string | Required and non-empty after trimming. |
| `source` | string | HTTPS `github.com/<publisher>/<repository>` URL with no query or fragment. |
| `source_revision` | string | Required 40-character lowercase hexadecimal Git commit. |
| `hermes_version_constraint` | string or omitted | When present, exact `>=A.B.C,<X.Y.Z` form. |
| `skills` | non-empty list | Complete installable catalog. Names must be unique; catalog order is installation order. |
| `skills[].name` | string | Required lowercase slug and exact installed name. |
| `skills[].install` | string or omitted | External provider; must begin with the source publisher/repository and end with `name`. Mutually exclusive with `bundled`. |
| `skills[].content_digest` | string or omitted | Required with `install`: SHA-256 of the complete canonical bundle produced by Hermes installation. Upstream files Hermes does not install are excluded. Forbidden with `bundled`. |
| `skills[].bundled` | string or omitted | Plugin-bundled provider; must exactly equal `name`. Mutually exclusive with `install`. |
| `lifecycle.human_gate_after` | string | Declared stage occurring before `implement`. |
| `lifecycle.stages` | non-empty list | Exactly the required lifecycle in order. |
| `lifecycle.stages[].id` | string | Required, non-empty, and unique. |
| `lifecycle.stages[].skills` | non-empty list | At least one skill per stage. |
| `lifecycle.stages[].skills[].name` | string | Exact reference to one catalog name; duplicate names in one stage are rejected. |
| `lifecycle.stages[].skills[].activation` | string | Required `required` or `conditional`; there is no compatibility default. |

The required lifecycle is:

```text
define -> plan -> implement -> verify -> review -> deliver
```

The pack-declared human gate is plan-approval metadata between `plan` and
`implement`, not a separate stage. The runtime's attended review disposition is
also ledger-owned and pack-neutral: it occurs after structured `review`, creates
`deliver` only for exact acceptance, and may instead create a revision-addressed
Plan card that requires fresh approval.

At graph creation, every executable stage becomes one Hermes Kanban card pinned
with `daidala:orchestrate` plus the exact catalog names bound to that stage. Only
stage-bound skills are loaded as candidates. Catalog-only skills remain
installable, inspectable, and readiness-controlled without being activated by a
worker. After `kanban_show`, the worker records
a `daidala.skill-activation/v1` manifest before stage methodology or evidence:
`required` skills must be applicable or blocked, while `conditional` skills may
be applicable, deferred, not applicable, or blocked. Approval and attended
review disposition are ledger-owned policy metadata between stages; neither has
a Kanban card or worker skills. Profiles, card links, workspaces, activation
decisions, and `daidala.handoff/v1` metadata use pack-neutral runtime contracts.

Each stage may bind at most 32 skills, matching the activation tool and artifact
bounds. Missing or unknown `activation` values, unknown catalog names, duplicate
catalog names, and provider fields inside a stage binding fail pack validation.
Schema version 2 has no migration reader for version 1.

External card skills use their exact `name`. A `bundled` skill is loaded through
the plugin namespace as `daidala:<name>`; for example, the AI-DLC worker card
pins `daidala:aidlc-adapter`.

## Runtime model

Successful validation produces frozen dataclasses:

- `CatalogSkill(name, install, content_digest, bundled)`;
- `StageSkill(name, activation)`;
- `Stage(id, skills)`;
- `WorkflowPack(name, source, source_revision, hermes_version_constraint,
  skills, stages, human_gate_after)`.

`WorkflowPack.lifecycle` derives the ordered stage tuple. Unknown keys are not
preserved and must not be treated as supported extensions.

## Installation and readiness

`daidala packs validate <pack>` proves pack shape only.

`daidala packs install <pack>` defaults to a mutation-free plan that resolves
each external catalog declaration to an immutable raw `SKILL.md` URL at the
declared `source_revision`, checks the bounded Hermes version, scans
profile-local installed names, verifies Hermes-installed-bundle digests, and
prints every intended `hermes skills install … --yes` mutation. `--apply`
executes only an unblocked plan and post-verifies that every catalog name became
installed. Missing or disabled catalog skills block workflow start, including
catalog-only entries. Installation never changes an existing disabled state. A digest mismatch is
reported in `revision_mismatches` as an integrity warning, but does not block
installation, pack use, or workflow start; Daidala never silently replaces the
installed skill.

The supported pack-installation contract accepts the complete pinned catalog.
`--recursive` is therefore a refused capability, not a local glob expansion.

## Implemented pack

`addyosmani` declares all 24 skills from the self-contained
[forgegod/addyosmani-agent-skills](https://github.com/forgegod/addyosmani-agent-skills)
fork in its installable catalog and maps 20 of them onto the six stages. It is
pinned at the commit and per-skill digests declared in
`daidala/packs/addyosmani.yaml`; the mapping remains data, not a Python special
case. `aidlc` declares one packaged provider and maps it onto every stage:
`daidala:aidlc-adapter` skill because stable AI-DLC v1.0.1 publishes editor
rules rather than externally installable Hermes skills. Both provider forms
use the same catalog and stage-binding machinery.

## Source of truth and tests

- Runtime validator: `daidala/packs.py`
- Installation and revision mechanism: `daidala/skills.py`, `daidala/cli.py`
- Bundled adapters: `daidala/packs/addyosmani.yaml`, `daidala/packs/aidlc.yaml`
- Validation tests: `tests/test_packs.py`
- Activation-policy tests: `tests/test_workflow.py`, `tests/test_execution.py`
- Installation tests: `tests/test_skill_installation.py`
