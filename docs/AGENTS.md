# docs/

## Purpose

Own current architecture documentation, the numbered reading set, and executable implementation plans.

## Ownership

- `README.md` is the only reading-order, support-status, and symptom-routing index.
- `00-getting-started.md` owns the executable first-run operator walkthrough.
- `01-architecture.md` owns process and component boundaries.
- `02-workflow-state.md` owns the Daidala policy ledger, Hermes Kanban state
  authority, and transition-ownership contract.
- `03-pack-reference.md` owns the workflow-pack schema and activation modes.
- `04-authoring-packs.md` owns pack-neutral adapter and activation authoring.
- `05-lifecycle-stages.md` owns executable stage inputs, activation, outputs,
  and gates.
- `06-security.md` owns current trust, activation-audit, and unavailable-control
  boundaries.
- `08-hermes-integration.md` owns verified Hermes versions, discovery paths, and installation limitations.
- `09-pack-adapters.md` owns implemented pack mappings, activation policy, and
  divergences.
- `10-autonomous-development-use-cases.md` owns user-oriented task selection,
  skill handoffs, steering controls, tutorial ideas, and future use cases.
- `11-skill-usage-and-user-control.md` owns the design contract for card-scoped
  candidate loading, persisted activation, cross-stage handoff, and user
  selection boundaries.
- `12-market-overview.md` owns source-backed evaluation of candidate workflow
  packs, interoperability standards, optional integrations, and adjacent
  products.
- `13-autonomous-triggering.md` owns the how-to contract for admitting external
  work through Hermes cron and webhooks without weakening Daidala approval.
- `14-workflow-constraints.md` owns the implemented workflow-scoped policy artifact,
  the policy-versus-methodology boundary, and skill-backed reusable sources.
- `15-self-improvement.md` owns the comprehensive technical flow for the
  generic autonomous self-improvement protocol and its first Daidala instance,
  including identities, modes, transitions, authority, adapters, evidence,
  persistent-knowledge boundaries, increment-document provenance,
  reconciliation, recovery, and exercised operator procedures.
- `16-self-improvement-setup.md` owns the executable environment prerequisite
  checklist, observed blocker states, controller/board/gateway/container/GitHub
  setup boundaries, stable CLI check IDs, and ready-to-admit gate for the Daidala
  dogfood instance. It remains normative when a checker is implemented.
- `evaluation-results/` owns versioned, redacted evaluation definitions and
  observed case records; its child contract prevents unrun behavior from being
  reported as evidence.
- `plans/` contains self-contained plans for future implementation sessions.

## Local Contracts

- Plans name exact files, verification gates, stop conditions, and unresolved decisions.
- Describe the current intended design without iteration diaries or stale migration breadcrumbs.
- Runtime claims must be grounded in Daidala source or current official Hermes documentation.
- Future numbered documents appear as unlinked support-status entries until their behavior exists.
- Runtime documents name their source-of-truth modules and verification tests.
- Use repository-relative links locally and authoritative upstream URLs for external claims.
- A prerequisite checker mirrors `16-self-improvement-setup.md`; it never becomes
  an independent checklist or substitutes a passing report for human approval.
- `16-self-improvement-setup.md` remains the single complete reproduction guide
  for controller setup, credentials, GitHub projection, gateway, evaluator,
  trusted evidence, and the ready-to-admit gate. Do not split required operator
  steps into session history or implementation plans alone.

## Work Guidance

- Update the active plan when a design decision changes before implementation begins.
- Move stable implemented contracts into normal architecture/operator docs rather than leaving the plan as the only source.
- Give new operators one user-centric, executable starting path before directing
  them to architecture or reference material. State what starts the workflow,
  what must remain running, what the user observes, and which action comes next.
- Keep deterministic behavior distinct from skill or model judgment.
- Do not publish operator commands until they have been exercised against the supported Hermes version.

## Verification

```bash
python scripts/check_md_links.py .
```

- Confirm Mermaid diagrams show Daidala inside the existing Hermes process, never as a server.
- Audit runtime claims against `daidala/`, `tests/`, and current official Hermes documentation.

## Child DOX Index

| Child | Owns | Read when editing… |
|---|---|---|
| [`evaluation-results/AGENTS.md`](evaluation-results/AGENTS.md) | Versioned experiment limits, stable cases, redacted evidence, and result records. | Evaluation definitions, statuses, evidence, or findings. |

See [`/AGENTS.md`](../AGENTS.md).
