# 14 — Workflow constraints

> Status: implemented. The artifact and interfaces described here are enforced
> by the policy ledger, service, tool, and CLI boundaries.

Workflow constraints give one Wingstaff workflow durable user-defined policy
that applies across definition, planning, implementation, verification, review,
and delivery. They complement the initial goal: the goal says what to accomplish;
constraints state what must remain true while accomplishing it.

The phase-gated implementation record is
[`plans/2026-07-12-workflow-constraints.md`](plans/2026-07-12-workflow-constraints.md).

## Scope

Constraints belong to one workflow. A workflow records its named Hermes board,
while its constraints remain independent of global board configuration. Two
workflows on the same board may use different packs and constraints. The same
pack or reusable constraint source may be selected by workflows on different
boards.

A workflow pack is also selected per workflow. The difference between a pack and
constraints is therefore authority and content, not binding scope:

| Control | Scope | Owns |
|---|---|---|
| Initial goal | One workflow | Requested outcome |
| Hermes profile | Multiple runs and workflows | General worker model, tools, and instructions |
| Workflow pack | One selected workflow, reusable across boards | Phase methodology and required/conditional skill activation |
| Workflow constraints | One selected workflow, optionally materialized from a reusable source | Policy invariants and approval boundaries |
| Definition and plan | One workflow revision | Produced scope and implementation design |
| Kanban comment | One card thread | Human steering and retry context |

Constraints must exist before definition, survive plan replacement, and change
under their own revision. Embedding them only in the plan would leave definition
ungoverned and couple policy identity to implementation scope.

## Policy is not methodology

This boundary prevents constraints from becoming a stripped-down skill system.

Constraints may express:

- prohibitions, such as no commit, push, deployment, or unapproved dependency;
- approval requirements;
- properties required of outputs, such as documentation matching public contract
  changes;
- quality or release boundaries, such as unresolved critical security findings
  blocking delivery.

Constraints may not express:

- procedures, ordered steps, or development methodology;
- TDD, debugging, decomposition, review, or research techniques;
- skill, pack, profile, model, or tool selection;
- shell commands or tool calls;
- activation modes, ranks, or overrides;
- permissions or exceptions to higher-level policy.

Methodology belongs in a skill and its workflow-pack mapping. General worker
behavior belongs in a Hermes profile. Constraint text cannot grant tools,
credentials, commit/push authority, or exceptions to Wingstaff, Hermes,
repository, pack, or system policy.

The schema rejects executable configuration structurally: fields such as
`skills`, `pack`, `profiles`, `models`, `tools`, `steps`, `commands`, and
`activation` are unknown and invalid. Arbitrary prose cannot be classified
perfectly without pretending that a semantic judgment is deterministic. A worker
that encounters methodology-like constraint prose must record a blocked result
and ask the user to move that content into a skill or pack. Wingstaff can prove
which text and digest governed a run; it cannot prove that arbitrary prose is
semantically policy-only.

Examples:

| Suitable constraint | Belongs in a skill or pack instead |
|---|---|
| Do not add a production dependency without explicit approval. | Use TDD and write a failing test before implementation. |
| Unresolved critical security findings block delivery. | Run this command sequence and diagnose failures in this order. |
| Documentation must match changed public contracts. | Use the architecture-review skill during planning. |
| Never commit, push, or deploy. | Decompose implementation into vertical slices. |

## Constraint artifact

The schema is `wingstaff.workflow-constraints/v1`:

```yaml
schema: wingstaff.workflow-constraints/v1
global:
  - Never commit or push.
  - Do not add production dependencies without explicit approval.
phases:
  review:
    - Unresolved critical security findings block delivery.
  deliver:
    - |-
      Documentation must match changed public contracts and describe
      any required operator action.
```

Each constraint is a YAML string. Plain and quoted scalars are accepted for short
constraints. Literal block scalars (`|-`) preserve line breaks; folded block
scalars (`>-`) apply YAML's folding rules. The example uses plain scalars for
short constraints and `|-` for a multiline constraint without a trailing
newline. Explicit YAML tags are rejected.

`global` applies to every executable phase. A `phases` entry augments the global
list only for that phase. Valid phase keys are `define`, `plan`, `implement`,
`verify`, `review`, and `deliver`.

The implementation must reject unknown fields, duplicate keys, aliases, merge
keys, custom tags, non-string values, control characters, and oversized content.
Global and per-phase lists contain at most 16 constraints. Each parsed constraint
contains 1–1,024 UTF-8 bytes after normalization, and canonical constraint
content contains at most 4,096 UTF-8 bytes. It canonicalizes the validated model
as normalized JSON and computes SHA-256 over the canonical UTF-8 bytes. List
order and the parsed scalar content are meaningful; scalar style, indentation,
and mapping order are not.

The supported Hermes v0.18.2 host preserves a task body through 8,192 characters
in worker context and visibly truncates larger bodies. Wingstaff therefore also
rejects any fully rendered card body over 8,192 characters. The smaller
canonical-content limit leaves room for workflow identity, goal, pack, plan,
worktree, and worker instructions and remains safe for multibyte text. Oversized
content is rejected rather than truncated.

## Persistence and projection

Each accepted constraint version becomes an immutable workflow-owned artifact.
The Wingstaff policy ledger stores an append-only reference containing revision,
path, digest, and recording time. Historical artifacts are never overwritten.
A workflow without constraints has explicit null identity and no implied
defaults.

Every executable card receives a delimited `Workflow constraints` section with:

- workflow ID and named board;
- constraint revision and digest;
- immutable artifact path;
- all global constraints;
- only the current phase's constraints;
- an instruction to block on methodology-like content or conflicts rather than
  weakening higher-level policy.

Constraints remain separate from the card's pack-stage skill candidate list,
activation modes, and attention ranks. Successful and blocked handoffs and every
Wingstaff evidence operation carry the current constraint revision and digest. A
worker attached to a stale card cannot submit current evidence.

## Approval and replacement

Human approval covers the exact current tuple:

```text
(plan_revision, plan_digest, constraints_revision, constraints_digest)
```

Changing constraint content is a policy revision, not a comment edit. A changed
revision:

1. preserves the previous immutable artifact;
2. invalidates approval and stale activation/evidence eligibility;
3. removes any Wingstaff-owned implementation worktree through its existing
   ownership guard;
4. archives obsolete cards through public Hermes operations;
5. creates a fresh `define -> plan` graph under the new policy revision;
6. requires regenerated definition and plan artifacts;
7. requires renewed exact plan-and-constraint approval.

Semantically identical content is idempotent and performs none of those actions.
The replacement result must report approval, card, and worktree consequences
explicitly.

## Reusable sources

Reusable constraint sources use exact installed Hermes policy skills for
distribution and reuse. Wingstaff:

- requires standard YAML frontmatter followed by exactly one fenced `yaml`
  constraint document and rejects any other body prose or fence;
- verifies the caller-supplied SHA-256 digest of the complete installed skill
  directory before reading `SKILL.md`;
- snapshots canonical constraint content into the workflow artifact;
- records source name and digest as provenance;
- keeps that source outside pack methodology activation and ranking;
- remains operable if the installed source later changes or disappears.

Hermes skills provide reusable distribution. Wingstaff adds workflow
materialization, revision, approval, and evidence binding. The reusable source
stays outside pack methodology activation and ranking.

Reusable sources and one-off content use the same validation, materialization,
persistence, projection, approval, and replacement path. One-off input uses an
explicit constraints file or inline content; no interface infers a path or source
name from arbitrary text.

## Conflict correction

When constraint text conflicts with required methodology or attempts to prescribe
methodology:

1. inspect the constraint artifact, activation artifact, and Kanban comment;
2. move procedural guidance into an appropriate skill or pack mapping;
3. replace the workflow constraints if policy changes, accepting graph restart;
4. regenerate and reapprove the current plan-and-constraint tuple.

Generic `hermes kanban unblock` does not resolve the policy conflict or restore
Wingstaff approval.

## Security and failure behavior

- Constraint text is delimited policy data, never executable configuration.
- Full content is never truncated.
- Source provenance and workflow constraint identity are distinct.
- Materialized workflow artifacts are self-contained and do not require their
  reusable source to remain installed.
- Ledger invalidation becomes durable before stale host work is cleaned up.
- Public Hermes Kanban operations are the only card boundary; Wingstaff does not
  import host internals or access Kanban SQLite.
- Constraints cannot weaken existing commit, push, approval, or evidence policy.

## Source of truth

- Concept and usage: this document
- Executable plan: `docs/plans/2026-07-12-workflow-constraints.md`
- Artifact and ledger models: `wingstaff/state.py`
- Deterministic transitions: `wingstaff/workflow.py`
- Coordination and persistence: `wingstaff/service.py`, `wingstaff/execution.py`
- Card projection: `wingstaff/kanban.py`
- Existing skill inventory and digest verification: `wingstaff/skills.py`
- Reusable-source adapter: `wingstaff/constraints.py` with exact installed-skill
  verification from `wingstaff/skills.py`
- Tool and CLI surfaces: `wingstaff/schemas.py`, `wingstaff/tools.py`,
  `wingstaff/cli.py`
- Verification: workflow, store, tool, CLI, Kanban, worker-contract, and execution
  tests under `tests/`
