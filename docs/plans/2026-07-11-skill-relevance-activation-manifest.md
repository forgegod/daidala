# Skill relevance activation manifest implementation plan

> Status: Done.
>
> Baseline: `65e6085` (`docs: explain autonomous skill selection and
> handoffs`).
>
> Phase 0 completed as a source-read-only feasibility check. Renewed human
> approval authorized Phase 1 implementation. Phases remain checkpointed and
> advance only after their verification gate and commit succeed.

## Goal

Make Wingstaff distinguish between skills that a pack makes mandatory and skills
that are candidates whose `Use When` criteria must be assessed for the concrete
card. The worker contract requires a validated, durable skill activation manifest
before stage methodology begins. Wingstaff deterministically refuses stage
evidence operations when the current manifest is missing, invalid, pending, or
reports a blocked capability. Wingstaff cannot prove when methodology application
began; it proves that activation decisions existed before evidence was accepted.

Keep Hermes Kanban as the worker lifecycle and keep all candidate skills loaded
for now. Do not add a daemon, selector card, nested Hermes process, profile-local
hook dependency, or external classification service.

## Honest assessment

The current implementation is coherent but too coarse. It proves which skills
were loaded, not whether those skills were appropriate for the task or compatible
with the stage contract. This is already a correctness problem, not only a token
cost:

- `test-driven-development` is loaded during `verify`, although its normal
  code-writing loop conflicts with Wingstaff's immutable captured scope;
- browser verification, debugging, security, performance, migration,
  observability, and CI/CD guidance are conditional but currently load as if
  every card needed them;
- Addyosmani's `Use When` and `When NOT to Use` instructions are available to the
  model but Wingstaff neither requires an explicit decision nor records one;
- an auditor can reconstruct the candidate list but not why the worker applied
  or ignored an individual skill.

The implementation should therefore be adapted. The adjustment is worth doing
because workflow packs and exact skill provenance are core Wingstaff value, and
broad unconditional mappings weaken that value.

The profile-local `pre_llm_call` proposal is not the right production design for
this feature:

- it runs after Hermes has loaded every card skill;
- its output is ephemeral and absent from the ledger and handoff;
- hook errors are fail-open;
- every assignee profile would need identical configuration;
- it would move a pack-level policy decision into host-local setup.

A `pre_llm_call` hook remains useful for unrelated ephemeral context enrichment.
It is not required for skill relevance classification because the worker already
has the pinned skill documents and receives card and parent context through
`kanban_show`.

## Design decision

Implement Wingstaff-native, pre-work activation assessment:

```text
Hermes loads orchestrate + all stage candidate skills
                         |
                    kanban_show
                         v
worker evaluates required + conditional skills against:
Use When / When NOT / stage policy / available capability
                         |
          wingstaff_record_skill_activation
                         v
validated immutable activation artifact + ledger reference
                         |
worker contract permits methodology; evidence operation becomes legal
                         |
handoff includes activation artifact digest and active skill names
```

This is a deterministic gate on *accepting stage evidence*, not a pre-spawn
filter or a tool-execution sandbox. The worker contract requires assessment before
applying methodology, but Wingstaff cannot deterministically prevent or timestamp
earlier reads, edits, or commands. It does not claim to reduce initial prompt
size. Pre-spawn filtering is a separate future optimization that would require a
supported Hermes spawn-transform boundary or progressive creation of each stage
card.

## Pack contract

### Explicit activation mode

Every pack skill entry gains a required `activation` field:

```yaml
- name: test-driven-development
  install: addyosmani/agent-skills/skills/test-driven-development
  content_digest: ...
  activation: conditional
```

Allowed values:

- `required` — pack policy says the skill must be applied in this stage; the
  worker may not demote it;
- `conditional` — the worker classifies it using the pinned skill's `Use When`,
  `When NOT to Use`, capability requirements, and Wingstaff stage policy.

Do not add a compatibility default. Both bundled packs must declare the field
explicitly, and pack validation must reject missing or unknown values. The
project is pre-release and should have one unambiguous schema.

`wingstaff:orchestrate` remains unconditionally required by the engine and is not
part of the pack activation decision.

### Initial bundled-pack mapping

Use conservative defaults:

- Addyosmani:
  - `define`: `spec-driven-development` required; interview and idea refinement
    conditional;
  - `plan`: planning and task breakdown required;
  - `implement`: all four specialist skills conditional because their own
    positive and negative criteria depend on the approved task;
  - `verify`: all verification specialists conditional;
  - `review`: code review required; simplification, security, and performance
    conditional;
  - `deliver`: delivery specialists conditional because Wingstaff records
    readiness but does not commit, push, migrate, or deploy.
- AI-DLC: the bundled stage-aware adapter required in every executable stage.

Validate this mapping against the pinned Addyosmani skill content during Phase 1.
If a skill's own loading constraints contradict its assigned worker capabilities,
classify that as a pack defect rather than weakening the activation gate.

### Criteria source

Do not parse the external repository README at runtime and do not copy its table
into the pack. The canonical criteria are inside the exact installed skill
directory already covered by the content digest:

- frontmatter description;
- `When to Use`;
- `When NOT to Use`;
- loading and capability constraints.

The activation artifact records the worker's matched criteria as quoted or tight
paraphrases. Wingstaff validates structure and provenance, not semantic truth;
judgment remains with the host model.

## Activation manifest contract

Persist the full immutable `ActivationManifest` as JSON using schema
`wingstaff.skill-activation/v1`:

```json
{
  "schema": "wingstaff.skill-activation/v1",
  "workflow_id": "workflow-123",
  "stage": "implement",
  "plan_revision": 0,
  "pack": "addyosmani",
  "pack_source_revision": "0123456789abcdef0123456789abcdef01234567",
  "sequence": 1,
  "supersedes_digest": null,
  "decisions": [
    {
      "name": "test-driven-development",
      "skill_digest": "...",
      "activation_mode": "required",
      "category": "applicable",
      "rank": 1,
      "matched_criteria": ["the approved plan changes behavior"],
      "evidence": ["plan.md requires a regression test"],
      "rationale": "Behavior changes require the pinned test-first feedback loop.",
      "condition": null
    }
  ]
}
```

Pack obligation and runtime disposition are separate dimensions:

- `activation_mode` is server-owned and copied from the selected pack. It is
  `required` or `conditional`; the worker does not supply or override it.
- `category` is the worker judgment: `applicable`, `deferred`,
  `not_applicable`, or `blocked`.
- A required entry may be `applicable` or `blocked` only. This represents a
  missing capability or policy conflict honestly without demoting pack policy.
- A conditional entry may use any category.

Category meanings:

- `applicable` — the skill applies now and may be used;
- `deferred` — the conditional skill may be applied only if its recorded
  condition occurs during the stage;
- `not_applicable` — current task evidence or negative criteria exclude it;
- `blocked` — the skill is required or relevant but cannot be applied because a
  capability is missing or its actions conflict with current stage policy.

`deferred` conditions are model-authored prose and are not interpreted by the
engine. If a deferred skill is later applied or its trigger is observed, the
worker must record a superseding manifest changing that decision to `applicable`
or `blocked` before submitting stage evidence. Wingstaff enforces the resulting
manifest at the evidence boundary; it does not claim to detect arbitrary prose
conditions independently.

### Artifact and ledger models

Use two explicit immutable models:

- `ActivationManifest` owns complete JSON validation, canonical serialization,
  decisions, provenance, identity, sequence, and supersession data. Its canonical
  bytes determine the artifact digest.
- `ActivationManifestReference` is the compact ledger fact. It contains stage,
  plan revision, sequence, path, digest, state (`pending` or `finalized`),
  `blocked`, and `supersedes_digest`. Rationale, criteria, and evidence remain in
  the artifact rather than being duplicated in the ledger.

The ledger has at most one effective finalized reference for each stage and plan
revision. Superseded manifests remain immutable and inspectable. References form
a linear sequence beginning at 1: each changed reference points to the immediately
preceding digest, with no forks, gaps, or cycles.

### Bounds

The tool schema and Python validator use the same explicit limits:

- at most 32 decisions, while exact pack-stage coverage still applies;
- `name`: 1–128 characters and the existing canonical skill slug syntax;
- `matched_criteria` and `evidence`: 1–8 strings each, each 1–500 characters;
- `rationale`: 1–1,000 characters;
- `condition`: null except for `deferred`, where it is 1–500 characters;
- `rank`: a positive integer no greater than the number of decisions;
- `supersedes_digest` and all digests: lowercase SHA-256 hexadecimal;
- no unknown object properties at any level.

Pack validation must reject a stage with more than 32 skills so workers are not
given an impossible manifest contract.

### Validation and canonical equality

The deterministic validator must require:

1. The call comes from the Kanban card recorded for the same workflow, stage, and
   plan revision. Read the host-owned `HERMES_KANBAN_TASK` and
   `HERMES_KANBAN_BOARD` process environment, require both, and compare them with
   the ledger's board and current `card_for(stage)`. The handler `task_id` kwarg
   is turn-isolation state, not Kanban identity. Do not trust a model-supplied
   task ID or board.
2. Every exact pack-stage skill appears once and only once.
3. No undeclared or substituted entry appears. `wingstaff:orchestrate` is injected
   by the engine rather than declared by the pack, is outside the activation
   decision set, and must never appear as a manifest decision.
4. Skill digests and activation modes are copied from the ledger and pack;
   neither is trusted model input.
5. Required entries use `applicable` or `blocked` only.
6. Conditional entries use `applicable`, `deferred`, `not_applicable`, or
   `blocked`.
7. `applicable` decisions have contiguous unique positive ranks from 1 through
   the number of applicable decisions. Other decisions have no rank.
8. `deferred` decisions have a non-empty condition; all other decisions have a
   null condition.
9. Every decision has non-empty bounded criteria, evidence, and rationale.
10. A manifest with any `blocked` decision is persisted for audit, but all stage
    evidence operations remain denied until an unblocked manifest supersedes it.
    Pending or otherwise unfinalized references also deny evidence acceptance.
11. Server-owned identity and provenance fields match the current ledger and pack.
    `pack_source_revision` is the pack's bare 40-character lowercase Git commit,
    matching `WorkflowLedger.pack_source_revision`; the pack source URL remains
    available through the selected pack and is not duplicated in the manifest.
12. Supersession is linear and names the immediately preceding effective digest.

The worker supplies only `workflow_id`, `stage`, `supersedes_digest`, and decision
fields `name`, `category`, `rank`, `matched_criteria`, `evidence`, `rationale`, and
`condition`. The service enriches all other fields.

For idempotency, canonicalize model-owned decision input by preserving pack skill
order and list item order, normalizing no prose, rejecting unknown fields, and
serializing with sorted object keys and fixed JSON separators. Compare this
canonical decision payload with the latest artifact while excluding server-owned
sequence, path, digest, timestamp, and supersession fields. An identical request
returns the existing reference and allocates no sequence. A changed request must
name the latest digest in `supersedes_digest`; missing or stale values are rejected
before persistence. Array order is meaningful serialization input. `rank` is
relative attention order, not a relevance score or confidence percentage.

## Ledger and policy behavior

Add immutable ledger references for activation artifacts. Full decisions live in
immutable JSON artifacts. The ledger exposes `activation_for(stage)` as the latest
effective finalized reference for the current stage revision.

Revision rules:

- `define` and `plan` activations use revision `0`, matching their cards;
- approval has no activation;
- post-gate activations use the current plan revision;
- plan replacement leaves historical activation artifacts intact, while current
  accessors ignore obsolete post-gate revisions.

Before these operations succeed, require a current, finalized, unblocked
activation manifest for the matching stage. This is the deterministic enforcement
boundary; earlier methodology ordering is a worker-contract requirement:

| Stage | Gated operation |
|---|---|
| Define | `wingstaff_submit_artifact(stage: "define")` |
| Plan | `wingstaff_submit_artifact(stage: "plan")` |
| Implement | `wingstaff_capture_implementation` |
| Verify | `wingstaff_record_verification` |
| Review | `wingstaff_submit_artifact(stage: "review")` |
| Deliver | `wingstaff_deliver` |

The manifest gate does not mirror Kanban status. When a manifest reports
`blocked`, the worker contract requires a focused comment and `kanban_block`;
Hermes remains the operational authority.

### Atomic persistence and recovery

Persistence must not overwrite an artifact when concurrent workers derive the
same sequence:

1. Load the latest ledger and canonicalize the request. Return its existing
   reference immediately when it is identical.
2. Under optimistic concurrency, validate supersession, reserve the next
   sequence, and append a pending reference. A failed compare-and-swap reloads
   state and retries validation; it never writes a file.
3. Create the deterministic stage/revision/sequence JSON file exclusively.
   `ExecutionWorkspace` must reject an existing destination rather than overwrite
   through `Path.write_text`.
4. Finalize the reference under optimistic concurrency only after the file digest
   matches its canonical bytes.
5. If creation or finalization fails, evidence operations reject the pending
   reference. A retry with identical canonical input may finish it when the
   exclusive file has the expected digest. Conflicting content is a hard policy
   error requiring operator remediation or cancellation.

Only finalized references authorize evidence. Tests cover compare-and-swap races,
exclusive-create collisions, write and finalize failures, and safe recovery. No
failure path may overwrite an artifact or let a pending reference authorize
evidence.

## User influence and retry behavior

The user does not directly edit categories or bypass pack-required skills.
Steering remains durable and reviewable:

1. Inspect the activation artifact through Wingstaff status or its artifact path.
2. Comment with missing context, a capability correction, or a policy decision.
3. Reassign the card if a different profile is needed.
4. Unblock the card.
5. The replacement worker calls `kanban_show`, evaluates the new evidence, and
   records a superseding manifest before resuming stage work.

This preserves the pack contract while allowing human correction of model
judgment.

## Explicit non-goals

- no `pre_llm_call` shell hook or Python hook bundled by Wingstaff;
- no new Hermes hook or Kanban lifecycle hook;
- no selector cards or extra lifecycle stages;
- no secondary LLM call, classifier service, or nested `hermes chat` process;
- no runtime parser for arbitrary Markdown headings in external skills;
- no pre-spawn removal of conditional skills;
- no per-workflow user override of skill names or pack-required modes;
- no confidence scores or hidden relevance thresholds;
- no compatibility reader for ledgers written before this unreleased schema
  change.

## Phase 0 — verify the Hermes worker identity boundary

### Objective

Prove the supported Hermes v0.18.2 host context used to bind an activation call
to the executing Kanban card. This is a read-only feasibility gate, not
implementation authorization.

### Sources and files

- current official Hermes plugin and Kanban documentation;
- installed Hermes v0.18.2 handler-dispatch source;
- `tests/test_plugin.py` and `tests/test_tools.py` for a later contract test;
- this plan, to record the authoritative source and exact host context shape.

### Steps

1. Trace tool registration through invocation and record the exact handler and
   process context, value types, and lifecycles for host-owned Kanban identity.
2. Verify whether identity is absent for calls outside a Kanban worker and require
   those calls to fail closed.
3. Specify a contract test using the real host context rather than the current
   invented `task_id="test"` fixture convention.
4. Confirm the value can be compared with the current card selected from the
   ledger's `card_references`; Phase 2 may expose this existing lookup through the
   planned `WorkflowLedger.card_for(stage)` helper. Do not accept a model-authored
   task ID.
5. If reliable identity is not exposed, stop. Amend and re-approve this plan with
   an explicit alternative binding; never weaken the check to workflow ID plus a
   model-supplied stage.

### Gate

Phase 0 gate: GREEN against Hermes Agent v0.18.2 at commit
`7acaff5ef2bcbaa22bd23b72efe60906123a4f55`.

Repository gate passed with 26 Markdown files, 129 tests, Ruff, both bundled
pack validations, build, Twine, release-content audit, Lefthook validation, and
unstaged/staged diff checks.

The expected handler-kwarg identity does not exist. The supported boundary is
the dispatcher-owned process environment:

- The official worker-lane contract names `HERMES_KANBAN_TASK` as the executing
  card ID and `HERMES_KANBAN_BOARD` as its board slug. The v0.18.2 dispatcher
  writes `task.id` and the resolved board into those variables before spawning
  `hermes -p <assignee> chat -q ...` in `hermes_cli/kanban_db.py`.
- Normal plugin dispatch forwards a handler kwarg named `task_id`, but
  `agent/turn_context.py` defines it as an optional caller value or a generated
  UUID for per-turn terminal/browser isolation. The dispatcher-spawned quiet CLI
  calls `run_conversation` without a `task_id`, so this kwarg is not the Kanban
  card ID. `tools/registry.py` forwards the kwarg unchanged to
  `handler(args, **kwargs)`.
- Outside a dispatcher-spawned Kanban worker, both Kanban environment variables
  are absent. The activation handler must fail closed when either is absent or
  blank, even if its `task_id` kwarg has a value.
- The activation handler must read both environment variables itself, pass them
  separately to the service, and compare them with `WorkflowLedger.board_slug`
  and `WorkflowLedger.card_for(stage).task_id`. It must never accept either value
  in model-owned tool arguments.
- Phase 3 contract tests must set and clear the two environment variables around
  calls through the registered handler, pass an unrelated turn-isolation
  `task_id` kwarg, and cover absent context, wrong board, wrong card, and the
  matching current card. Existing `WorkflowLedger.card_for(stage)` already
  selects revision 0 for define/plan and the current plan revision afterwards.

This reliable alternative binding satisfies the feasibility gate without a
Hermes change. Renewed human approval remains required before Phase 1 and all
source changes.

## Phase 1 — make activation intent part of packs

### Objective

Distinguish mandatory methodology from conditional candidate skills without
changing card dispatch.

### Files

- `wingstaff/packs.py`
- `wingstaff/packs/addyosmani.yaml`
- `wingstaff/packs/aidlc.yaml`
- `wingstaff/tools.py`
- `tests/test_packs.py`
- `tests/test_tools.py`
- `tests/test_plugin.py`
- `wingstaff/AGENTS.md`

### Steps

1. Add a `SkillActivationMode` enum and `activation` field to `SkillRef`.
2. Update both bundled packs with the explicit mapping above, then enable
   rejection of missing and unknown modes in `_validate_skill`. Keep the
   validator and both YAML updates in one commit so no committed checkpoint has
   an impossible pack schema.
3. Extend `wingstaff_pack_info` to report each skill's canonical name, provider,
   digest provenance, and activation mode instead of reducing the response to an
   install-target string.
4. Add tests for required fields, invalid modes, exact bundled mappings, and
   pack-info JSON.
5. Update `wingstaff/AGENTS.md` to state that pack entries declare required or
   conditional activation while the engine remains pack-neutral.

### Gate

```bash
pytest tests/test_packs.py tests/test_tools.py
ruff check wingstaff/packs.py wingstaff/tools.py tests/test_packs.py tests/test_tools.py
wingstaff packs validate addyosmani
wingstaff packs validate aidlc
```

Phase 1 gate: GREEN — exact required/conditional mappings were checked against
the pinned Addyosmani skill descriptions; focused tests passed with 22 tests;
the repository gate passed with 26 Markdown files, 133 tests, Ruff, both pack
validations, build, Twine, release-content audit, Lefthook validation, and diff
checks. The public pack-info contract also had an older bundled-provider
assertion in `tests/test_plugin.py`; keeping that regression aligned belongs in
this phase because the output shape changed here.

Commit only after the gate passes:

```text
feat(packs): declare required and conditional stage skills
```

## Phase 2 — begin the ship-locked activation migration

### Objective

Add activation state and persistence as the first checkpoint of one ship-locked
migration. Phases 2–4 must not be released, merged independently, or considered
usable until the Phase 4 gate and full `pytest` pass. No evidence transition is
gated before the recording tool and worker instructions exist.

### Files

- `wingstaff/state.py`
- `wingstaff/workflow.py`
- `wingstaff/execution.py`
- `tests/test_workflow.py`
- `tests/test_execution.py`
- `wingstaff/AGENTS.md`
- `tests/AGENTS.md`

### Steps

1. Add `ActivationManifest`, decision, and `ActivationManifestReference`
   immutable dataclasses with strict serialization and the bounds above. The
   reference serializes and validates its `pending` or `finalized` state.
2. Add pending/finalized append-only references to `WorkflowLedger`, including
   duplicate, revision, sequence, linear-supersession, and recovery validation.
3. Add `activation_for(stage)` and exact stage-revision helpers.
4. Add a pure `record_skill_activation` workflow transition that validates the
   manifest against the selected `WorkflowPack` and ledger skill digests.
5. Implement `_require_stage_activation`, but do not enable it on evidence
   transitions until Phase 4 completes the recording and worker contract. Keep
   approval exempt.
6. Add exclusive JSON creation and the pending/finalized persistence protocol
   with deterministic stage/revision/sequence filenames.
7. Ensure plan replacement preserves history but ignores obsolete current-stage
   activation references.
8. Add positive, idempotency, supersession, serialization, missing-manifest,
   blocked-manifest, wrong-stage, wrong-skill, and wrong-category tests.
9. Update owning DOX contracts for the new policy fact and test responsibility.

### Gate

```bash
pytest tests/test_workflow.py tests/test_execution.py
ruff check wingstaff/state.py wingstaff/workflow.py wingstaff/execution.py tests/test_workflow.py tests/test_execution.py
```

Phase 2 gate: GREEN — strict canonical activation models, exact pack-stage
validation, linear pending/finalized references, idempotent finalization,
blocked supersession, and exclusive artifact creation passed 29 focused tests.
The repository gate passed with 26 Markdown files, 138 tests, Ruff, both pack
validations, build, Twine, release-content audit, Lefthook validation, and
unstaged/staged diff checks. Evidence transitions remain ungated until Phase 4.

Commit only after the gate passes:

```text
feat(policy): persist stage skill activation manifests
```

## Phase 3 — expose one strict worker operation

### Objective

Let the assigned stage worker submit a validated manifest through the normal
Wingstaff tool boundary.

### Files

- `wingstaff/schemas.py`
- `wingstaff/tools.py`
- `wingstaff/service.py`
- `wingstaff/__init__.py`
- `tests/test_tools.py`
- `tests/test_plugin.py`
- `tests/test_execution.py`

### Steps

1. Add `wingstaff_record_skill_activation` with bounded nested JSON schema for
   workflow ID, stage, superseded digest, and decisions.
2. Preserve handler `args: dict, **kwargs` and JSON-string return behavior.
3. Read `HERMES_KANBAN_TASK` and `HERMES_KANBAN_BOARD` in the handler and pass
   them separately to the service. Reject absent or blank context, non-Kanban
   invocations, board mismatches, and mismatches with the current stage card.
   Ignore the turn-isolation `task_id` kwarg for authorization, and do not accept
   a task ID or board in tool arguments.
4. In the service, load the pinned pack, validate all candidates, enrich
   decisions with ledger digests and activation modes, canonicalize for
   idempotency, and use the pending/finalized atomic persistence protocol.
5. Return the stored manifest reference and current workflow in the tool result
   so the worker can include its digest in the eventual handoff.
6. Register the schema and handler through the existing plugin loop.
7. Add handler-boundary tests for malformed arrays, missing decisions, unknown
   skills, wrong card context, blocked persistence, supersession, and successful
   JSON responses.
8. Extend plugin registration tests to require the new tool exactly once.

### Gate

```bash
pytest tests/test_tools.py tests/test_plugin.py tests/test_execution.py
ruff check wingstaff/schemas.py wingstaff/tools.py wingstaff/service.py wingstaff/__init__.py tests/test_tools.py tests/test_plugin.py tests/test_execution.py
```

Phase 3 gate: GREEN — 31 focused tests cover strict nested input, host-owned
Kanban board/card authorization, blocked supersession, idempotency, and
optimistic-concurrency recovery. The service now stores the pack's bare pinned
commit because the previous URL-qualified value could not satisfy the Phase 2
manifest contract. The isolated local-Git plugin probe loaded 11 tools with no
plugin error. The repository gate passed with 27 Markdown files, 141 tests,
Ruff, both pack validations, build, Twine, release-content audit, Lefthook
validation, and diff checks.

Commit only after the gate passes:

```text
feat(plugin): record worker skill activation decisions
```

## Phase 4 — make activation part of the worker and handoff contract

### Objective

Require relevance assessment after card inspection and before stage work, and
carry its digest across worker boundaries.

### Files

- `wingstaff/workflow.py`
- `wingstaff/service.py`
- `wingstaff/AGENTS.md`
- `wingstaff/skills/orchestrate/SKILL.md`
- `tests/AGENTS.md`
- `tests/test_workflow.py`
- `tests/test_store.py`
- `tests/test_tools.py`
- `tests/test_worker_contract.py`
- `tests/test_kanban.py`
- `tests/test_execution.py`

### Steps

1. Change the worker sequence to:
   `kanban_show` → inspect relevant parent artifacts → classify all pack-stage
   skills → `wingstaff_record_skill_activation` → stage work.
2. Define the four categories (`applicable`, `deferred`, `not_applicable`, and
   `blocked`), the separate required/conditional activation modes, rank semantics,
   evidence requirements, and blocked behavior in the orchestration skill.
3. State explicitly that loaded skills are candidates, `wingstaff:orchestrate`
   is always required, and workers must not discover replacements.
4. Require every successful `wingstaff.handoff/v1` to include
   `skill_activation_digest` and the active skill names.
5. Require blocked workers to cite the activation digest and blocked skill in the
   Kanban comment and block reason.
6. Keep Kanban card skill lists unchanged: orchestrate plus the full exact stage
   candidate list. Add regression tests proving no selector cards or hidden host
   operations appear.
7. Update cross-pack execution fixtures to record manifests before each stage
   operation. Prove Addyosmani can mix required and conditional activation modes
   with applicable, deferred, not-applicable, and blocked categories while AI-DLC
   keeps its required adapter applicable.
8. Enable `_require_stage_activation` on all six evidence transitions only after
   the recording tool and worker instructions are present.
9. Prove missing, pending, or blocked manifests stop stage artifacts without
   fabricating a completion handoff. Prove a triggered deferred skill requires a
   superseding manifest under the worker contract before evidence submission.
10. Run the full test suite; Phases 2–4 remain one ship-locked change until it
    passes.

### Gate

```bash
pytest tests/test_worker_contract.py tests/test_kanban.py tests/test_execution.py
ruff check tests/test_worker_contract.py tests/test_kanban.py tests/test_execution.py
```

Phase 4 gate: GREEN — the worker contract now requires card inspection followed
by exact skill activation before methodology or evidence, and successful
handoffs carry the finalized activation digest and active skill names. Missing,
pending, and blocked manifests fail closed at all six evidence boundaries;
cross-pack execution covers Addyosmani's required/conditional category mix and
AI-DLC's required adapter path. The focused gate passed 48 tests. The repository
gate passed with 28 Markdown files, 147 tests, Ruff, both pack validations,
build, Twine, release-content audit, Lefthook validation, and diff checks. The
isolated staged-tree directory-plugin probe loaded 11 tools with no plugin error.

Commit only after the gate passes:

```text
feat(workers): gate stage evidence on skill relevance
```

## Phase 5 — reconcile operator and design documentation

### Objective

Document implemented behavior without claiming pre-spawn filtering or hook-based
enforcement.

### Files

- `docs/03-pack-reference.md`
- `docs/04-authoring-packs.md`
- `docs/05-lifecycle-stages.md`
- `docs/06-security.md`
- `docs/09-pack-adapters.md`
- `docs/10-autonomous-development-use-cases.md`
- `docs/11-skill-usage-and-user-control.md`
- `docs/README.md`
- `docs/AGENTS.md`
- `wingstaff/AGENTS.md`
- `tests/AGENTS.md`

### Steps

1. Define required versus conditional pack entries and migration-free validation.
2. Update lifecycle diagrams to include activation between `kanban_show` and
   stage work, without adding a lifecycle stage.
3. Explain the persisted manifest, supersession, human correction, and blocked
   capability path.
4. Correct the current wording that all mapped skills are simply applied
   together: they are all loaded, but only active or triggered deferred guidance
   should be applied.
5. Keep `pre_llm_call` documented as an advisory context extension, not the
   Wingstaff gate.
6. Add the activation artifact to security and audit-boundary documentation.
7. Complete the DOX pass and refresh ownership text where policy or verification
   responsibilities changed.

### Gate

```bash
python scripts/check_md_links.py .
git diff --check
```

Phase 5 gate: GREEN — operator and design documentation now distinguishes loaded
candidates from active guidance, documents the persisted manifest and
supersession path, and keeps `pre_llm_call` advisory. The DOX ownership pass,
Markdown table structure audit, and link check passed across 28 Markdown files.
The repository gate passed with 147 tests, Ruff, both pack validations, build,
Twine, release-content audit, Lefthook validation, and diff checks.

Commit only after the gate passes:

```text
docs: explain persisted skill relevance activation
```

## Final verification

Run the complete repository gate after all phase commits:

```bash
lefthook validate
pytest
ruff check .
wingstaff packs validate addyosmani
wingstaff packs validate aidlc
rm -rf dist build *.egg-info
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
python scripts/check_md_links.py .
git diff --check
git status --short --branch
git log -6 --format='%h %s%nAuthor: %an <%ae>'
```

Do not mark the implementation done if any command fails, if a stage evidence operation
can succeed without a current finalized activation manifest, if a blocked or
pending manifest permits evidence acceptance, or if a handoff omits its
activation digest.

Final verification: GREEN — Lefthook validation, 147 tests, Ruff, both pack
validations, build, Twine, release-content audit, the 28-file Markdown link
check, and diff checks passed. Commits `443b5a7` through `43658eb` form the
verified implementation sequence. Pre-existing operator-document changes in
`docs/AGENTS.md`, `docs/README.md`, `docs/12-market-overview.md`, and
`docs/13-autonomous-triggering.md` remain outside this plan's commits.

## Acceptance criteria

- Every pack skill explicitly declares `required` or `conditional` activation.
- Every executable stage has exactly one effective finalized activation manifest
  for its current stage/revision before its evidence operation can succeed;
  superseded history remains immutable and forms a linear, fork-free chain.
- Manifest decisions cover the exact pack-stage candidate set and exact pinned
  digests.
- Required pack skills cannot be demoted by model judgment.
- Blocked decisions persist evidence and fail closed; required skills may report
  `blocked` without being demoted from pack-required policy.
- The worker contract requires activation before methodology, while deterministic
  enforcement is explicitly limited to evidence acceptance.
- Superseding decisions preserve history and require the prior digest.
- Hermes Kanban remains the sole operational-status authority.
- Card dispatch continues to load the full exact stage candidate set.
- No profile hook, external selector service, selector card, nested Hermes
  process, or pack-specific engine branch is introduced.
- Handoffs expose the activation digest and active skill names.
- Both bundled packs pass the same engine and execution tests.
- Documentation distinguishes loaded candidates, active guidance, and future
  pre-spawn filtering.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The model invents criteria or evidence. | Require source-grounded strings and preserve outcome verification; do not present the manifest as proof of semantic correctness. |
| Activation becomes ceremony with boilerplate decisions. | Keep the schema compact, rank only active skills, and test realistic cross-pack examples rather than accepting empty rationale. |
| A skill is relevant but incompatible with the stage. | Use `blocked`, persist the reason, and require Kanban remediation instead of silently ignoring the conflict. |
| Human comments change relevance after the first attempt. | Append a superseding manifest bound to the previous digest; never overwrite history. |
| A deferred condition occurs after initial assessment. | Require a superseding `applicable` or `blocked` decision before evidence submission; do not claim the engine interprets prose triggers. |
| Concurrent or interrupted persistence corrupts history. | Reserve under optimistic concurrency, create artifacts exclusively, finalize only after digest verification, and deny pending references. |
| A future Hermes host stops exposing trustworthy worker card or board identity. | Fail closed when `HERMES_KANBAN_TASK` or `HERMES_KANBAN_BOARD` is absent or mismatched; re-run Phase 0 and require plan amendment and renewed approval before adapting to another boundary. |
| Ledger schema change breaks stale local data. | The runtime is unreleased; use one fresh schema and no compatibility reader, consistent with the existing replacement rule. |
| All candidate skills still consume prompt context. | State this limitation explicitly. Do not add selector cards or unsupported dispatcher hooks merely to optimize tokens. |
| Pack authors mark everything required. | Authoring guidance must require justification; bundled mappings and tests provide conservative examples. |

## Future work deliberately deferred

Revisit pre-spawn filtering only if Hermes exposes a supported fail-closed
transform that can alter a claimed task's skill list before command construction,
or if Wingstaff later creates each stage card only after predecessor evidence is
available. Any such change must consume the same persisted activation schema and
must not depend on profile-local hooks.

Possible later extensions:

- aggregate activation categories and outcomes for pack-quality telemetry;
- compare manifests across profiles or models;
- let pack authors provide structured machine-readable criteria in addition to
  the pinned skill prose;
- authorize a signed user override as a new pack revision rather than an
  invisible per-run mutation.
