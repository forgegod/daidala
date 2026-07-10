# 03 — Workflow-pack reference

This document describes only schema version 1 as implemented by
`wingstaff/packs.py`. Planned fields such as source revisions, artifacts,
transitions, verification commands, and gate policy objects are not accepted or
preserved by the current runtime model.

## Location and loading

Bundled packs live at `wingstaff/packs/<name>.yaml` and are loaded with
`importlib.resources`, so package and source-tree access use the same code path.
`load_pack(name)` accepts a non-empty conservative slug containing only
alphanumeric characters and hyphens, appends `.yaml`, and rejects an unknown
resource.

## Schema version 1

```yaml
schema_version: 1
name: example
source: https://github.com/publisher/skills
lifecycle:
  human_gate_after: plan
  stages:
    - id: define
      skills:
        - name: requirements-skill
          install: publisher/repository/skills/requirements-skill
    - id: plan
      skills:
        - name: planning-skill
          install: publisher/repository/skills/planning-skill
    - id: implement
      skills:
        - name: implementation-skill
          install: publisher/repository/skills/implementation-skill
    - id: verify
      skills:
        - name: verification-skill
          install: publisher/repository/skills/verification-skill
    - id: review
      skills:
        - name: review-skill
          install: publisher/repository/skills/review-skill
    - id: deliver
      skills:
        - name: delivery-skill
          install: publisher/repository/skills/delivery-skill
```

## Field contract

| Path | Type | Implemented requirement |
|---|---|---|
| `schema_version` | integer | Must equal `1`. |
| `name` | string | Required and non-empty after trimming. |
| `source` | string | Required and non-empty after trimming. Schema v1 does not validate it as a URL or pin a revision. |
| `lifecycle` | mapping | Required. |
| `lifecycle.human_gate_after` | string | Required, must name a declared stage, and must occur before `implement`. |
| `lifecycle.stages` | non-empty list | Must contain exactly the required lifecycle in order. |
| `lifecycle.stages[].id` | string | Required, non-empty, and unique. |
| `lifecycle.stages[].skills` | non-empty list | At least one skill reference per stage. |
| `lifecycle.stages[].skills[].name` | string | Required and non-empty. |
| `lifecycle.stages[].skills[].install` | string | Required and non-empty; the final slash-separated segment must equal `name`. |

The exact required stage order is:

```text
define -> plan -> implement -> verify -> review -> deliver
```

Discovery is part of the product lifecycle but not a schema-v1 skill-bearing
stage. The human gate is metadata between stages, not a stage record.

## Runtime model

Successful validation produces frozen dataclasses:

- `SkillRef(name, install)`;
- `Stage(id, skills)`;
- `WorkflowPack(name, source, stages, human_gate_after)`.

`WorkflowPack.lifecycle` derives the ordered tuple of stage IDs. Schema v1
ignores unknown YAML keys because the validator reads only known fields; they
must not be treated as supported extensions.

## Failure behavior

Validation raises `PackError` for malformed structure or invariant violations.
The plugin handler catches `PackError` and returns a JSON error object. The
standalone diagnostics command prints a JSON error and exits non-zero. Neither
path invents a replacement pack.

Schema v1 does not:

- fetch or install external skills;
- prove that a named external skill exists;
- pin or resolve an upstream revision;
- execute a lifecycle stage;
- persist artifacts or approval;
- validate arbitrary extra keys.

## Implemented pack

`addyosmani` maps the six stages to install-target strings under
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills). It places
the human gate after `plan`. The mapping is data, not a special Python branch.

## Source of truth and tests

- Runtime validator: `wingstaff/packs.py`
- Bundled adapter: `wingstaff/packs/addyosmani.yaml`
- Positive and invariant tests: `tests/test_packs.py`
- Tool-boundary tests: `tests/test_plugin.py`
