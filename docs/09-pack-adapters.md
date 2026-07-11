# 09 — Pack adapters

Pack adapters map external skill sets onto Wingstaff's pack-neutral lifecycle.
The engine validates common mechanics only; skill selection and sequencing live
in bundled pack YAML. Both adapters expand into the same approval-gated Kanban
graph and `wingstaff.handoff/v1` worker contract; only the pinned stage skills
and their judgment differ.

## Implemented adapters

| Pack | Upstream source | Pinned revision | Human gate |
|---|---|---|---|
| `addyosmani` | `https://github.com/addyosmani/agent-skills` | `7ce442de03ddc1b72480c3b48d55c62880ea2a90` | After `plan` |
| `aidlc` | `https://github.com/awslabs/aidlc-workflows` | `e49341dbeb8af82758dd85e96ed7fe9bcf38a447` (`v1.0.1`) | After `plan` |

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
install targets. Pack installation dry-runs missing-skill mutations by default
and requires exact complete-directory digests before workflow start.

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

## AI-DLC mapping

Stable AI-DLC v1.0.1 is MIT-0 licensed and distributes a core workflow plus
rule-detail directories for coding harnesses. It does not distribute Agent
Skills. Wingstaff therefore packages one attributed `aidlc-adapter` skill and
references it through the generic `bundled` provider field in every stage.
Worker cards load it by its Hermes plugin-qualified name,
`wingstaff:aidlc-adapter`.

| Wingstaff stage | AI-DLC concept and artifact intent |
|---|---|
| Define | Inception intent analysis, requirements, constraints, and acceptance criteria. |
| Plan | Inception design/decomposition plus the selected Construction execution plan. |
| Implement | Construction code generation in the approved Wingstaff worktree. |
| Verify | Construction build and test commands with exact evidence. |
| Review | Requirements, design, security, diff, and evidence review. |
| Deliver | Reviewed changed paths and release-readiness evidence; no implicit deployment. |

AI-DLC's generated `aidlc-state.md` and `audit.md` are not adopted because
Wingstaff already owns durable state and approval. Stable Operations is a
placeholder and does not justify invented deployment behavior. The v2 preview
is not embedded: it requires a complete harness overlay and owns an independent
orchestration engine, state machine, hooks, and workspace state.

The same temporary-repository fixture executes both packs through
`WorkflowService`; there is no `aidlc` conditional in core workflow code.

## Current limitations

- Publisher signatures are not available; integrity is commit and content-hash based.
- Hermes v0.18.2 cannot recursively install a repository, so Wingstaff refuses
  `--recursive` and installs only the required subset.
- Updates are plans only when installed content differs; Wingstaff never
  silently replaces a skill during an active workflow.
- Stable AI-DLC rules are adapted, not copied wholesale; upstream methodology
  changes require an explicit pinned adapter update.

## Source of truth

- Mappings: `wingstaff/packs/addyosmani.yaml`, `wingstaff/packs/aidlc.yaml`
- AI-DLC adapter and license: `wingstaff/skills/aidlc-adapter/`
- Pack model and validation: `wingstaff/packs.py`
- Exact skill gate: `wingstaff/skills.py`
- Pack-neutral execution: `wingstaff/service.py`, `wingstaff/execution.py`
- Verification: `tests/test_packs.py`, `tests/test_skills.py`,
  `tests/test_skill_installation.py`,
  `tests/test_execution.py`
