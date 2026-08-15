# Product capabilities

Capability records describe material behavior that is implemented now. They are concise, falsifiable indexes into runtime source, executable tests, and detailed architecture or operator contracts; they are not implementation plans.

## Current capabilities

| Capability | Status | Primary surface |
|---|---|---|
| [CAP-0001 — Approval-gated workflow execution](capabilities/CAP-0001-approval-gated-workflow-execution.md) | implemented | none; presented by CAP-0003 |
| [CAP-0002 — Git-pinned phased-plan admission](capabilities/CAP-0002-git-pinned-phased-plan-admission.md) | implemented | none; CLI and CAP-0003 adapters |
| [CAP-0003 — Operator dashboard](capabilities/CAP-0003-operator-dashboard.md) | implemented | [wireframe index](wireframes/index.html) |
| [CAP-0004 — GitHub repository registration](capabilities/CAP-0004-github-repository-registration.md) | implemented | Config → GitHub Repositories ([wireframe](wireframes/index.html)) |
| [CAP-0005 — Reviewed GitHub branch delivery](capabilities/CAP-0005-reviewed-github-branch-delivery.md) | implemented | Workflow detail → Branch delivery ([wireframe](wireframes/index.html)) |
| [CAP-0006 — Repository policy bootstrap](capabilities/CAP-0006-repository-policy-bootstrap.md) | implemented | Config → GitHub Repositories bootstrap ([wireframe](wireframes/index.html)) |
| [CAP-0007 — Complete workflow-pack installation](capabilities/CAP-0007-complete-workflow-pack-installation.md) | implemented | none; CLI adapter and future CAP-0003 presentation |

## Capability contract

- Use stable `CAP-NNNN` identities. Never reuse an ID.
- State only present-tense, user- or operator-observable behavior.
- Every implemented capability links runtime source and executable tests.
- Link detailed architecture, security, and runbook owners instead of copying their contracts.
- A primary human-facing screen or interaction links matching HTML and PNG artifacts under `wireframes/`.
- Update a CAP only when material behavior changes. Internal refactors do not churn capability records.
- Create or resume one active change record before implementing a material behavior change.

## Canonical shape

Each file under `capabilities/` contains:

1. `# CAP-NNNN: <title>`
2. `**Status:** implemented` or `deprecated`
3. `**Primary surface:** <surface>` or `none`
4. `## Outcome`
5. `## Behavior`
6. `## Evidence` with `### Runtime` and `### Tests`
7. `## Contracts`
8. `## Links`

Run the repository record check after changing any capability:

```bash
python scripts/check_records.py .
```
