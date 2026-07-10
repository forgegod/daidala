# 09 — Pack adapters

Pack adapters map external skill sets onto Wingstaff's pack-neutral lifecycle.
The engine validates common mechanics only; skill selection and sequencing live
in bundled pack YAML.

## Implemented adapters

| Pack | Upstream source | Pinned revision | Human gate |
|---|---|---|---|
| `addyosmani` | `https://github.com/addyosmani/agent-skills` | `7ce442de03ddc1b72480c3b48d55c62880ea2a90` | After `plan` |

## Addyosmani mapping

| Stage | Exact skills |
|---|---|
| Define | `interview-me`, `idea-refine`, `spec-driven-development` |
| Plan | `planning-and-task-breakdown` |
| Implement | `incremental-implementation`, `test-driven-development`, `source-driven-development`, `doubt-driven-development` |
| Verify | `test-driven-development`, `debugging-and-error-recovery`, `browser-testing-with-devtools` |
| Review | `code-review-and-quality`, `code-simplification`, `security-and-hardening`, `performance-optimization` |
| Deliver | `git-workflow-and-versioning`, `ci-cd-and-automation`, `documentation-and-adrs`, `observability-and-instrumentation`, `shipping-and-launch`, `deprecation-and-migration` |

`test-driven-development` is intentionally referenced by both implement and
verify. The prerequisite check deduplicates exact names while preserving their
first lifecycle position.

Every install target is fully qualified as
`addyosmani/agent-skills/skills/<exact-name>`. A similar name does not satisfy
the requirement. Missing requirements block workflow creation and list their
install targets. Phase 6 dry-runs missing-skill installation by default and
requires exact complete-directory digests before workflow start.

## Adapter and engine boundary

The Addyosmani adapter does not add conditionals to Python. All packs share:

- the ordered `define`, `plan`, `implement`, `verify`, `review`, `deliver`
  lifecycle;
- one human gate after plan and before implementation;
- exact skill-name and install-target validation;
- the same artifact, worktree, verification, review, and delivery mechanics.

A pack-specific behavior belongs in YAML or its orchestration instructions. A
capability needed by multiple packs requires a shared schema extension and
pack-neutral validation.

## Current limitations

- Publisher signatures are not available; integrity is commit and content-hash based.
- Hermes v0.18.2 cannot recursively install a repository, so Wingstaff refuses
  `--recursive` and installs only the required subset.
- Updates are plans only when installed content differs; Wingstaff never
  silently replaces a skill during an active workflow.
- The AI-DLC adapter belongs to Phase 9 and is not implemented.

## Source of truth

- Mapping: `wingstaff/packs/addyosmani.yaml`
- Pack model and validation: `wingstaff/packs.py`
- Exact skill gate: `wingstaff/skills.py`
- Pack-neutral execution: `wingstaff/service.py`, `wingstaff/execution.py`
- Verification: `tests/test_packs.py`, `tests/test_skills.py`,
  `tests/test_skill_installation.py`,
  `tests/test_execution.py`
