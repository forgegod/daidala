# docs/

## Purpose

Own current architecture documentation, the numbered reading set, product and
change records, and historical implementation plans.

## Ownership

- `README.md` is the only reading-order, support-status, and symptom-routing index.
- `00-getting-started.md` owns the executable first-run operator walkthrough.
- `01-architecture.md` owns process and component boundaries.
- `02-workflow-state.md` owns the Daidala policy ledger, immutable artifact
  identity versus active/archive availability, Hermes Kanban state authority,
  and transition-ownership contract.
- `03-pack-reference.md` owns the workflow-pack schema and activation modes.
- `04-authoring-packs.md` owns pack-neutral adapter and activation authoring.
- `05-lifecycle-stages.md` owns executable stage inputs, activation, outputs,
  gates, and terminal artifact-curation eligibility.
- `06-security.md` owns current trust, activation-audit, artifact archive/recovery,
  Cron, and unavailable-control boundaries.
- `07-runbook.md` owns the executable operator lifecycle for installation,
  initialization, prerequisite diagnosis, pack readiness, workflow start/status,
  exact plan approval, exact attended review disposition, reviewed branch delivery,
  plan-revision recovery,
  exact artifact list/show/export/archive/restore, curator scheduling,
  cancellation, upgrade, and native/standalone CLI parity.
- `08-hermes-integration.md` owns verified Hermes versions, discovery paths, and installation limitations.
- `09-pack-adapters.md` owns implemented pack mappings, activation policy, and
  divergences.
- `10-autonomous-development-use-cases.md` owns user-oriented task selection,
  skill handoffs, steering controls, tutorial ideas, and future use cases.
- `11-skill-usage-and-user-control.md` owns the design contract for card-scoped
  candidate loading, persisted activation, cross-stage handoff, attended
  disposition, revision feedback, and user selection boundaries.
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
- `product/AGENTS.md` owns current capability records and CAP-linked static
  wireframes.
- `changes/AGENTS.md` owns active material-change progress and archived receipts.
- `plans/AGENTS.md` owns immutable historical plans, shared family contracts,
  and their legacy UX design sources and review renders.

## Local Contracts

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
  steps into session history or change records alone.
- Capability records state current falsifiable behavior and link runtime source,
  tests, and detailed documentation owners. Change records are the sole
  repository-tracked progress authority for future material work.
- Existing `plans/` content is historical. Do not add plans or rewrite their
  recorded status to represent current work.

## Work Guidance

- Move stable implemented contracts into normal architecture/operator docs and
  summarize observable outcomes in the affected capability record.
- Give new operators one user-centric, executable starting path before directing
  them to architecture or reference material. State what starts the workflow,
  what must remain running, what the user observes, and which action comes next.
- Keep deterministic behavior distinct from skill or model judgment.
- Do not publish operator commands until they have been exercised against the
  exact supported Hermes host matrix.

## Verification

```bash
python scripts/check_records.py .
python scripts/check_md_links.py .
```

- Confirm Mermaid diagrams show Daidala inside the existing Hermes process, never as a server.
- Audit runtime claims against `daidala/`, `tests/`, and current official Hermes documentation.

## Child DOX Index

| Child | Owns | Read when editing… |
|---|---|---|
| [`changes/AGENTS.md`](changes/AGENTS.md) | Active CHG progress and archived implementation receipts. | Material-change scope, sequencing, decisions, evidence, or closeout. |
| [`evaluation-results/AGENTS.md`](evaluation-results/AGENTS.md) | Versioned experiment limits, stable cases, redacted evidence, and result records. | Evaluation definitions, statuses, evidence, or findings. |
| [`plans/AGENTS.md`](plans/AGENTS.md) | Historical plans, shared plan-family contracts, Pen wireframe sources, and review renders. | Historical provenance, execution contracts, or legacy plan-owned design assets. |
| [`product/AGENTS.md`](product/AGENTS.md) | Current CAP behavior and CAP-linked static wireframes. | Capability outcomes, source/test evidence, or current screen references. |

See [`/AGENTS.md`](../AGENTS.md).
