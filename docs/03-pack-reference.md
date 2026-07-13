# 03 — Workflow-pack reference

This document describes schema version 1 as implemented by
`daidala/packs.py`. The schema is pack-neutral and includes pinned external
source and skill-content integrity fields.

## Location and loading

Bundled packs live at `daidala/packs/<name>.yaml` and are loaded with
`importlib.resources`, so package and source-tree access use the same path.
`load_pack(name)` accepts a conservative alphanumeric-and-hyphen slug and
rejects unknown resources.

## Schema version 1

```yaml
schema_version: 1
name: example
source: https://github.com/publisher/repository
source_revision: 0123456789abcdef0123456789abcdef01234567
hermes_version_constraint: ">=0.18.2,<0.19.0"
lifecycle:
  human_gate_after: plan
  stages:
    - id: define
      skills:
        - name: requirements-skill
          activation: required
          install: publisher/repository/skills/requirements-skill
          content_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    - id: plan
      skills:
        - name: planning-skill
          activation: required
          install: publisher/repository/skills/planning-skill
          content_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    - id: implement
      skills:
        - name: implementation-skill
          activation: conditional
          install: publisher/repository/skills/implementation-skill
          content_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    - id: verify
      skills:
        - name: verification-skill
          activation: conditional
          install: publisher/repository/skills/verification-skill
          content_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    - id: review
      skills:
        - name: review-skill
          activation: required
          install: publisher/repository/skills/review-skill
          content_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    - id: deliver
      skills:
        - name: delivery-skill
          activation: conditional
          install: publisher/repository/skills/delivery-skill
          content_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

## Field contract

| Path | Type | Implemented requirement |
|---|---|---|
| `schema_version` | integer | Must equal `1`. |
| `name` | string | Required and non-empty after trimming. |
| `source` | string | HTTPS `github.com/<publisher>/<repository>` URL with no query or fragment. |
| `source_revision` | string | Required 40-character lowercase hexadecimal Git commit. |
| `hermes_version_constraint` | string or omitted | When present, exact `>=A.B.C,<X.Y.Z` form. |
| `lifecycle.human_gate_after` | string | Declared stage occurring before `implement`. |
| `lifecycle.stages` | non-empty list | Exactly the required lifecycle in order. |
| `lifecycle.stages[].id` | string | Required, non-empty, and unique. |
| `lifecycle.stages[].skills` | non-empty list | At least one skill per stage. |
| `lifecycle.stages[].skills[].name` | string | Required lowercase slug and exact installed name. |
| `lifecycle.stages[].skills[].activation` | string | Required `required` or `conditional`; there is no compatibility default. |
| `lifecycle.stages[].skills[].install` | string or omitted | External provider; must begin with the source publisher/repository and end with `name`. Mutually exclusive with `bundled`. |
| `lifecycle.stages[].skills[].content_digest` | string or omitted | Required with `install`: SHA-256 of the complete canonical skill directory. Forbidden with `bundled`. |
| `lifecycle.stages[].skills[].bundled` | string or omitted | Plugin-bundled provider; must exactly equal `name`. Mutually exclusive with `install`. |

The required lifecycle is:

```text
define -> plan -> implement -> verify -> review -> deliver
```

The human gate is metadata between `plan` and `implement`, not a separate
stage.

At graph creation, every executable stage becomes one Hermes Kanban card pinned
with `daidala:orchestrate` plus the exact skills declared for that stage. All
declared skills are loaded as candidates. After `kanban_show`, the worker records
a `daidala.skill-activation/v1` manifest before stage methodology or evidence:
`required` skills must be applicable or blocked, while `conditional` skills may
be applicable, deferred, not applicable, or blocked. The approval card is
Daidala policy infrastructure and carries no worker skills. Profiles, card
links, workspaces, activation decisions, and `daidala.handoff/v1` metadata use
pack-neutral runtime contracts.

Each stage may declare at most 32 skills, matching the activation tool and
artifact bounds. Missing or unknown `activation` values fail pack validation;
schema version 1 has no migration reader for the unreleased older shape.

External card skills use their exact `name`. A `bundled` skill is loaded through
the plugin namespace as `daidala:<name>`; for example, the AI-DLC worker card
pins `daidala:aidlc-adapter`.

## Runtime model

Successful validation produces frozen dataclasses:

- `SkillRef(name, activation, install, content_digest, bundled)`;
- `Stage(id, skills)`;
- `WorkflowPack(name, source, source_revision, hermes_version_constraint,
  stages, human_gate_after)`.

`WorkflowPack.lifecycle` derives the ordered stage tuple. Unknown keys are not
preserved and must not be treated as supported extensions.

## Installation and readiness

`daidala packs validate <pack>` proves pack shape only.

`daidala packs install <pack>` defaults to a mutation-free plan that resolves
source `HEAD`, checks the bounded Hermes version, scans profile-local installed
names, verifies complete-directory digests, and prints every intended
`hermes skills install … --yes` mutation. `--apply` executes only an unblocked
plan and post-verifies disk state. Revision or digest mismatch blocks workflow
start and requires `update-plan`; active workflows are never silently updated.

Hermes v0.18.2 has no recursive installation flag. `--recursive` is therefore a
refused capability, not a local glob expansion.

## Implemented pack

`addyosmani` maps the six stages to
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), pinned at
the commit and per-skill digests declared in
`daidala/packs/addyosmani.yaml`. The mapping remains data, not a Python
special case. `aidlc` maps the same stages to the packaged
`daidala:aidlc-adapter` skill because stable AI-DLC v1.0.1 publishes editor
rules rather than externally installable Hermes skills. Both provider forms
use the same `SkillRef` and stage machinery.

## Source of truth and tests

- Runtime validator: `daidala/packs.py`
- Installation and revision mechanism: `daidala/skills.py`, `daidala/cli.py`
- Bundled adapters: `daidala/packs/addyosmani.yaml`, `daidala/packs/aidlc.yaml`
- Validation tests: `tests/test_packs.py`
- Activation-policy tests: `tests/test_workflow.py`, `tests/test_execution.py`
- Installation tests: `tests/test_skill_installation.py`
