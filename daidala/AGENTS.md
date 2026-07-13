# daidala/

## Purpose

Implement the Hermes plugin boundary, deterministic policy and artifact ledger,
workflow-pack adapters, and bundled orchestration skills.

## Ownership

| Path | Owns |
|---|---|
| `__init__.py` | Hermes tool, skill, and operator CLI registration. |
| `errors.py` | Policy-ledger, persistence, and host-boundary error hierarchy. |
| `state.py` | Immutable policy ledger, artifact evidence, Kanban identifiers, skill activation manifests, and strict serialization. |
| `workflow.py` | Deterministic policy checks and ledger updates; no operational status transitions. |
| `locations.py` | Profile-aware data-root resolution; never hard-codes `~/.hermes`. |
| `store.py` | SQLite-backed policy-ledger persistence with optimistic concurrency. |
| `service.py` | Repository preflight, approval-gated graph, artifact, worktree, and ledger coordination. |
| `skills.py` | Exact installed-skill inventory, content-digest verification, and mutation-free install planning. |
| `constraints.py` | Strict workflow-constraint YAML parsing, canonicalization, bounds, and digest identity. |
| `projects.py` | Strict committed project-manifest parsing, canonical identity, verification declarations, and mutation policy. |
| `registrations.py` | Trusted profile-local project registration structure, limits, manifest binding, and storage path. |
| `credentials.py` | Strict alias-to-environment credential bindings with no secret values or resolver inference. |
| `prerequisites.py` | Stable self-improvement checklist registry, retained capability evidence, bounded probes, and strict prerequisite reports. |
| `cycles.py` | Pure self-improvement cycle identity, metric kinds, outcomes, delegation evidence, and lesson-reuse evidence. |
| `increments.py` | Strict increment-document classification, producer provenance, canonical manifest, bounds, and digest. |
| `adapters.py` | Strict normalized intake, finding, notification, claim, and receipt records plus injectable protocols. |
| `controller.py` | Replay-safe cycle admission, manifest snapshots, deterministic workflow binding, immutable cycle storage, and receipt validation. |
| `reconciliation.py` | Two-authority claim recovery evidence and local pending-to-published finding synchronization. |
| `execution.py` | Profile-local artifacts, detached worktrees, and diff capture. |
| `kanban.py` | Public host-boundary adapter for the idempotent, approval-gated Hermes card graph. |
| `schemas.py` | Tool schemas exposed to the model. |
| `tools.py` | Strict JSON-returning plugin handlers; exceptions never cross into Hermes. |
| `packs.py` | Pack loading and deterministic validation. |
| `cli.py` | Shared `hermes daidala` and standalone operator command tree, lifecycle dispatch, pack operations, and subprocess mutation boundary. |
| `dashboard_backend.py` | Profile-safe dashboard read model, live Kanban snapshots, constraint previews, and typed compare-and-swap replacement adapter. |
| `recommendations.py` | Pure finite pending-decision and next-action derivation from ledger facts and live Kanban snapshots. |
| `setup_wizard.py` | Typed setup preview, confirmation gate, and documented Hermes board/profile inventory commands. |
| `packs/` | Skill-set-specific lifecycle mappings. |
| `skills/` | Namespaced read-only orchestration and guided-setup skills bundled with the plugin. |

## Local Contracts

- `register(ctx)` imports no Hermes internals; it uses only the documented plugin context API.
- Tool handlers never raise across the plugin boundary and always return JSON strings.
- Pack skills declare exactly one provider: a fully qualified external install
  target or a plugin-bundled skill with the same exact name.
- Every pack skill explicitly declares `required` or `conditional` activation;
  pack adapters own the mapping and the engine remains pack-neutral.
- Daidala coordinates any pack-defined, skill-backed work; bundled software
  packs are current adapters, not the engine's product boundary.
- Skill activation manifests are immutable, exact-pack decision artifacts whose
  pending/finalized ledger references form a linear supersession chain.
- Every stage evidence operation requires its current activation manifest to be
  finalized and unblocked; successful worker handoffs carry its digest and the
  active skill names.
- The activation tool authorizes from `HERMES_KANBAN_BOARD` and
  `HERMES_KANBAN_TASK` against the ledger's current stage card; handler `task_id`
  is turn isolation and never grants workflow authority.
- External packs pin a Git source revision, bounded Hermes version, and complete-directory digest per required skill.
- Standalone CLI inventory comes from the profile skill directory; it never imports Hermes runtime internals.
- Native and standalone operator commands share one parser and dispatch layer; setup and external installation remain dry-run by default.
- Self-improvement prerequisite diagnosis extends the shared `doctor` command,
  mirrors the stable check IDs owned by `docs/16-self-improvement-setup.md`,
  emits bounded redacted evidence, and has no fix/apply or setup-mutation mode.
- Credential aliases resolve only through explicit profile-local `environment`
  bindings. GitHub tokens exist only for the bounded child call as `GH_TOKEN`;
  command output and reports never include token-derived values.
- Constraint file and exact policy-skill inputs converge on the shared service
  path. Policy skills require a verified complete-directory digest and exactly
  one fenced `yaml` constraint document after frontmatter.
- A committed project manifest may narrow trusted registration but never grants
  local paths, credentials, board/profile authority, evaluator capability,
  notification authority, or release permissions.
- Project, registration, cycle, and increment schemas reject unknown fields,
  unbounded content, non-canonical identity, and stale or ambiguous provenance.
- Adapter code defines strict normalized records and protocols only; concrete
  network implementations remain separately gated. Admission validates all
  external claim and event-specific notification data before workflow dispatch.
- Self-improvement workflow IDs equal deterministic cycle IDs, transitively
  binding the workflow ledger to the immutable canonical manifest snapshot,
  expected baseline, canonical constraints, and complete stage-profile map.
- Finding synchronization stays locally pending until an adapter returns the
  same stable finding identity plus a verified remote identity and HTTPS URL.
- Hermes Kanban owns every operational status; Daidala persists no mirrored
  ready, running, blocked, done, or archived field.
- Dashboard reads live Kanban state through documented `hermes kanban` commands;
  unavailable host state is labeled and never replaced by cached status.
- Agent-facing Kanban integration uses `ctx.dispatch_tool`; native and standalone
  CLI handlers translate the same narrow adapter boundary into documented
  `hermes kanban` subprocess commands. Daidala never imports or writes Hermes'
  Kanban database.
- Native `start` uses `--default-profile`; `--profile` is reserved and consumed
  by the Hermes host before plugin subcommand parsing.
- Start validates one explicit named board and a complete executable-stage profile map before creating cards.

### Public start surface (single source of truth)

The argument names accepted by `daidala_start` and the CLI flags accepted
by `hermes daidala start` are an external contract: cron prompts, webhook
prompts, agent-driven admission, and operator shell invocations all consume
the same names. `schemas.py::START` defines the JSON schema the model sees;
`cli.py::start` defines the CLI flag set. The two are intentionally aligned.

- Tool parameters: `board_slug`, `target_repository`, `goal`, `stage_profiles`
  (object keyed by stage with values `define`, `plan`, `implement`, `verify`,
  `review`, `deliver`), `pack` (default `addyosmani`), `workflow_id`, and the
  mutually exclusive `constraints_content` or `constraints_skill` plus
  `constraints_skill_digest` source.
- CLI flags: positional `target_repository` and `goal`; `--board`, `--pack`,
  `--default-profile`, repeated `--stage-profile STAGE=PROFILE`, `--workflow-id`,
  and mutually exclusive `--constraints-file` or `--constraints-skill` with
  `--constraints-skill-digest`.
- `--default-profile` fills every executable stage whose per-stage override
  is omitted, so a prompt may list only the stages that differ from the
  default. Operators reading a snippet must not interpret missing
  `--stage-profile` entries as missing stages.

### Cross-document bindings (must stay synchronized)

The following documents restate parts of the start surface and therefore
share ownership of its names with `schemas.py` and `cli.py`. Editing the
names here without updating the consumers leaves operators with snippets
that no longer match the plugin:

- `docs/00-getting-started.md` — first-workflow shell example using
  `--board`, `--default-profile`, and `--stage-profile`.
- `docs/13-autonomous-triggering.md` — agent prompt bodies that name
  `board`, `pack`, `workflow_id`, target repository, and the full
  `stage_profiles` mapping; plus a direct `hermes daidala start` shell
  snippet using `--default-profile` with explicit per-stage overrides.
- `daidala/skills/orchestrate/SKILL.md` — instructs the orchestration
  worker to call `daidala_start` with the same argument names.

When `schemas.py::START` or `cli.py::start` changes any of these names,
update all four locations in the same commit (or commit series). The
The verification gate does not catch doc drift against the live schema; only
`ruff check daidala tests` and `daidala packs validate <pack>` run.
Add a unit test or schema assertion whenever feasible so the next rename
fails locally rather than in production.
- Every executable card pins `daidala:orchestrate` plus its exact pack-stage
  skills, so worker lifecycle instructions survive launcher-session exit.
- External card skills retain their exact unqualified names; plugin-bundled card
  skills use the `daidala:<name>` namespace required by Hermes skill loading.
- Card IDs and idempotency keys are persisted as policy facts; live card status is read from Kanban and never mirrored.
- Card references and skill-activation manifests bind the current policy revision
  and constraint digest. Card references also persist the named board and
  constraint revision. Executable card bodies include the immutable artifact identity,
  every global constraint, and only the current executable stage's constraints;
  approval cards receive no constraint projection, and oversized bodies fail
  instead of truncating policy.
- Worker activation validates the current board, current policy-bound card, and
  live assignee before methodology or evidence. Every worker evidence operation
  repeats that current-card check. A constraint revision makes prior cards and
  activation manifests historical without deleting them.
- Approval binds the exact current plan revision/digest and constraint
  revision/digest pair, including explicit null constraint identity. Constraint
  replacement persists invalidation before host cleanup, retains historical
  artifacts, removes only an owned worktree, archives obsolete cards, and
  recreates a fresh define-to-plan graph under the new policy revision.
- Stage artifacts and activation chains are policy-revision scoped so regenerated
  definition and plan evidence cannot resolve to a historical policy revision.
- The policy store uses one fresh schema and does not inspect or migrate the
  unreleased workflow-state database.
- The engine never substitutes guessed data when a model, skill, or verifier fails.
- Delivery and operator cancellation remove only their Daidala-owned detached
  worktree; captured artifacts remain durable.
- No server, listening socket, or nested Hermes process is part of this package.

## Work Guidance

- Add mechanism to Python and subject-matter mappings to `packs/*.yaml`.
- Keep self-improvement identity and classification models pure. Admission may
  write only immutable profile-local cycle artifacts and call injected host
  adapters; evaluator and retention side effects remain later gated boundaries.
- Register bundled skills with `ctx.register_skill`; do not copy them into the user's mutable skill store.
- `daidala:setup` remains dashboard-independent, previews the exact
  `schemas.py::START` request, and requires explicit confirmation before any
  setup mutation or workflow start.
- Keep third-party attribution and license text beside derived bundled adapters.
- Use `importlib.resources` so wheel and Git installations behave consistently.

## Verification

```bash
pytest
ruff check daidala tests
daidala packs validate addyosmani
```

## Child DOX Index

*(empty — resource directories do not have independent work contracts.)*

See [`/AGENTS.md`](../AGENTS.md).
