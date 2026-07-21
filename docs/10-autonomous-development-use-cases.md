# 10 — Autonomous development use cases

Daidala is useful when a development task should run without continuous human
attention but must not become an unaudited “prompt to production” operation. It
turns one goal into an approval-gated Hermes Kanban workflow whose workers use a
selected methodology, exchange durable evidence, and stop when human judgment is
required.

This guide starts from user situations rather than Daidala internals. Use the
[getting-started guide](00-getting-started.md) for commands and the
[lifecycle reference](05-lifecycle-stages.md) for the complete stage contract.
See [Skill usage and user control](11-skill-usage-and-user-control.md) for the
design behind pack selection, card-scoped skill loading, and handoff.

## Where Daidala adds value

A coding agent can edit files and run tests. That alone does not answer the
operational questions that appear when the user stops watching every tool call:

- Which methodology and skill content was used?
- What problem definition became the implementation plan?
- Did a human approve that exact plan?
- Did implementation stay isolated from the original checkout?
- Which diff was actually verified and reviewed?
- Can another worker continue without reconstructing context from prose?
- What happens when a worker lacks access, a test fails, or review rejects the
  result?

Daidala adds this missing control layer without replacing Hermes:

- workflow packs pin the stage-to-skill mapping and skill provenance;
- workers persist task-specific activation decisions before applying methodology;
- Hermes Kanban owns assignment, dependencies, execution, comments, retries,
  and recovery;
- Daidala binds approval to the current plan digest;
- implementation runs in a detached Daidala-owned worktree;
- immutable artifacts connect definition, plan, diff, verification, review,
  and delivery;
- delivery reports evidence but does not commit, push, merge, or deploy.

The result is not a claim that the model followed every sentence of an active
skill. It is a reproducible record of the candidates loaded, the task-specific
activation decisions, and the outputs that passed the workflow's policy gates.

## Choose work that fits autonomous execution

Start with a task whose success can be stated and checked. GitHub's guidance for
coding agents similarly recommends clear, well-scoped tasks with acceptance
criteria and identifies bug fixes, test coverage, documentation, accessibility,
and technical debt as useful starting points. It advises caution for ambiguous,
production-critical, security-sensitive, deeply domain-specific, and broadly
scoped work.

| Candidate task | Fit | Why |
|---|---|---|
| Focused bug with a reproduction and regression test | Strong | Definition and verification can be made concrete. |
| Incremental feature with explicit acceptance criteria | Strong | The plan gate catches scope or design disagreement before code exists. |
| Test coverage, documentation, or bounded technical debt | Strong | The expected changed paths and checks are usually reviewable. |
| Repository research followed by a proposed plan | Strong | Definition and planning can complete without authorizing implementation. |
| Large refactor inside one repository | Conditional | It needs explicit boundaries, architecture context, and reliable tests. |
| Security or authentication change | Conditional | Use specialist profiles and independent human review; Daidala does not provide a security sandbox. |
| Incident response or production repair | Weak | The workflow is intentionally deliberative and has no deployment authority. |
| Cross-repository migration | Unsupported | A workflow currently owns one target repository and one baseline. |
| Autonomous release or deployment | Unsupported | Delivery intentionally records `committed: false` and `pushed: false`. |

The practical rule is simple: autonomy works best when intent is explicit,
repository context is discoverable, and success is independently testable.
OpenAI's agent-harness reports make the same operational point: configured
environments, repository-local knowledge, worktree isolation, tests, and
feedback loops matter as much as model capability.

## Use case: delegate a bounded backlog item

Suppose the goal is:

> Add CSV export to the existing audit-log screen. Preserve current filtering,
> cover authorization and empty results, update operator documentation, and run
> the repository's frontend and API checks.

### 1. Select the methodology

Choose a pack when starting the workflow:

- `addyosmani` gives each stage a focused set of external candidates. Definition
  always requires specification while interview and refinement are conditional;
  implementation, verification, and delivery classify their specialist skills
  from the current task and evidence.
- `aidlc` loads the bundled `daidala:aidlc-adapter` at every stage. The card's
  stage tells the adapter whether to apply AI-DLC inception, planning,
  construction, verification, review, or delivery guidance.

Daidala also pins `daidala:orchestrate` to every executable card. That skill
supplies the common worker protocol: inspect the card first, work in the assigned
workspace, record evidence, and finish through Kanban completion or blocking.
Approval is a human ledger decision, not a card, and no worker may invoke it.

Skills are contextual instructions, not functions called in sequence. Every
mapped skill is loaded as a candidate. After `kanban_show`, the worker records
which candidates are applicable, deferred, not applicable, or blocked. Required
entries must be applicable or blocked; only applicable entries receive contiguous
attention ranks. Daidala validates and persists that decision but cannot prove
which paragraphs influenced the model's reasoning.

### 2. Let definition and planning run

The definition worker receives the goal, repository, selected pack, assigned
profile, and its exact skill candidates. It records a finalized activation
manifest before the definition artifact, then completes with a compact
`daidala.handoff/v1` record containing artifact references, activation digest,
active skill names, and workflow identity.

Completion makes the dependent planning card runnable. Its worker calls
`kanban_show`, reads the parent handoff, uses its own phase skills, and records a
content-addressed plan. Execution then waits on the exact ledger-owned approval
tuple; no approval or implementation card exists yet.

### 3. Review the plan, not just the prompt

The user now has a concrete control point. Check that the plan names:

- intended behavior and non-goals;
- affected components and data boundaries;
- authorization and migration concerns;
- expected tests and verification commands;
- documentation and operational effects.

Approve only the digest of the acceptable plan. A generic Kanban unblock does
not grant Daidala approval. This prevents a stale or silently changed plan
from authorizing implementation.

### 4. Observe implementation without sharing a checkout

After approval, Daidala creates one detached worktree at the recorded clean
baseline. The implementation worker changes only that worktree and captures:

- a binary-capable diff, including untracked implementation files;
- a changed-path manifest before tests create caches or build outputs.

That snapshot becomes the reviewed scope. Verification and review may inspect
the preserved worktree, but they must not silently expand the captured
implementation.

### 5. Receive an evidence-backed delivery

The verification worker records exact commands, exit codes, and output
references. The review worker evaluates the captured diff against the goal,
plan, and verification evidence. Delivery then reports the reviewed paths and
evidence while explicitly leaving commit and push to a separately authorized
operation.

The useful output is therefore more than “the agent says it is done.” It is a
chain from requested goal to approved plan to immutable diff to observed checks
to review decision.

## How the handoff survives worker boundaries

Each stage can run in a separate Hermes process and profile. Handoff does not
depend on one model retaining a long conversation.

```text
card body + parent metadata + artifact references
                         |
                    kanban_show
                         v
           inspect pinned skill candidates
                         |
       daidala_record_skill_activation
                         v
              stage worker + active skills
                         |
          Daidala artifact/evidence operation
                         |
       kanban_complete with daidala.handoff/v1
                         v
               dependent card becomes ready
```

The next worker receives small, structured metadata and follows references to
full artifacts, including the immutable activation manifest. Post-approval
workers also receive the same absolute worktree and baseline. If activation is
blocked, the worker cites the activation digest and blocked skill, then blocks
without fabricating a completion handoff. After remediation and unblock, the
replacement worker reads that thread and records a superseding manifest before
continuing.

This design addresses a common multi-agent failure mode: context is lost or
mutated when one model summarizes work for another. Daidala still relies on
model-authored artifacts, but their paths, digests, revision, workspace, and
verification evidence are durable and checked at the handoff boundary.

## How the user steers the workflow

| Control | When to use it | What it changes |
|---|---|---|
| Goal | Before start | The durable task intent shown to every stage. |
| Pack | Before start | The methodology and exact stage-to-skill mapping. |
| Default and per-stage profiles | Before start | Which Hermes profile, model, tools, and profile instructions execute each stage. |
| Plan approval | After planning | Whether the exact current plan may create implementation work. |
| Kanban comment | When a worker asks or blocks | Durable clarification or remediation visible on retry. |
| Activation correction | Before stage evidence | Human guidance on a blocked or deferred decision; the worker records a superseding manifest rather than editing history. |
| Reassignment | When another capability or independent reviewer is needed | The profile used for the next run of that card. |
| Unblock | After fixing a dependency or supplying input | Allows Hermes to retry the same card; it never substitutes for plan approval. |
| Cancel | At any point | Archives cards and removes only the Daidala-owned worktree. |
| Pack authoring | Before future workflows | Creates a reusable, validated skill mapping rather than a one-off override. |

There is intentionally no `--stage-skill` option. A workflow cannot silently add,
remove, or replace one skill from a validated pack. External skill directories
must match their pinned content digests, and bundled skills are tied to the
plugin version. This makes two runs of the same pack comparable, but it means
experimentation requires authoring or updating a pack.

## Use case: recover from a failed autonomous run

A deterministic test failure is not a reason to let the agent loop until it
finds a convenient green result.

1. The worker records the failed command and output through Daidala.
2. It comments with the workflow, stage, evidence references, and required
   decision.
3. It blocks the card as `needs_input` with a `verification-failed:` reason.
4. The user inspects the evidence, comments with the decision, and may reassign
   the card to a stronger verification profile.
5. Hermes unblocks and respawns the same card with its history and worktree.

Verification and review cannot repair the already captured diff. If the failure
requires code changes, the approved plan and implementation scope must be
revised rather than patched invisibly. The runtime contains plan-replacement
logic, but the current public CLI and plugin tools do not expose it. Today the
safe operator path is to cancel and start a new workflow with the corrected
goal or plan expectations.

This is an important limitation, not a documentation detail: recovery works for
missing access, transient host failures, rerunning valid checks, and supplying
review decisions; it is incomplete for an in-place code-rework cycle.

## Use case: separate specialist judgment

Assigning one profile to all stages is the simplest setup. Separate profiles are
useful when independence or capability matters more than configuration cost:

- an architecture profile for `define` and `plan`;
- an implementation profile with the required build tools;
- a verification profile with browser or integration-test access;
- a review profile that did not author the implementation.

The pack still determines the skills. Profiles determine who interprets them
and which host capabilities are available. Daidala validates that each
assignee profile exists before creating cards, but it does not currently declare
least-privilege tool or network policy in the pack.

## Repository readiness before increasing autonomy

A weak repository produces weak autonomous work regardless of orchestration.
Before delegating larger tasks, make these inputs discoverable and executable:

- concise repository and path-specific agent instructions;
- architecture and product decisions stored in the repository rather than only
  in chat or personal knowledge;
- deterministic setup, build, lint, and test commands;
- representative tests for important behavior and boundaries;
- local fixtures or safe test services instead of production credentials;
- logs, screenshots, traces, or browser checks when behavior cannot be inferred
  from unit tests;
- explicit ownership and review rules.

This is where Daidala's evidence boundary has leverage: it can preserve the
plan, diff, and command results, but it cannot manufacture missing acceptance
criteria or a reliable verifier.

## Measure value instead of counting generated code

Research does not support one universal productivity claim. METR's early-2025
study found a slowdown for experienced maintainers in its sampled tasks, while
its 2026 update says wider agent adoption and task-selection effects now make a
single speedup estimate unreliable. The practical lesson is to measure the
workflow in the environment where it is used.

Useful measures include:

- accepted deliveries divided by started workflows;
- human review and remediation time, not just agent runtime;
- verification failures and review rejection rate;
- escaped defects and rollback rate after human integration;
- cycle time from goal to accepted evidence;
- repeated blocks caused by missing repository context or tools;
- cost per accepted change;
- percentage of generated scope discarded before integration.

Daidala currently records artifacts and evidence needed for several of these
measures, but it does not aggregate operational metrics, token usage, model
cost, or outcome trends.

## Security and oversight

Autonomous coding combines untrusted text, repository content, shell tools,
network access, and credentials. OWASP describes excessive agency as the
combination of excessive functionality, permissions, or autonomy and recommends
minimum tool scope, minimum downstream permissions, independent authorization,
and human approval for high-impact actions. GitHub's coding-agent security model
similarly uses isolated branches, restricted credentials, audit logs, and human
review before merge.

Daidala contributes:

- exact skill provenance and content checks;
- clean-baseline enforcement and detached worktrees;
- plan-digest approval before implementation;
- immutable diff and evidence capture;
- no automatic commit, push, merge, or deployment;
- visible Kanban comments, blocks, assignment, and retries.

Daidala does not currently provide a sandbox, network firewall, secret broker,
per-stage tool allowlist, prompt-injection filter, signed agent commits, or
publisher signatures for skill packs. Those controls must come from Hermes,
the selected profiles, repository tooling, and downstream review policy.

## Suggested tutorial series

These are documentation ideas, not an implementation plan. The first five can
be written against current behavior; the rest should wait for the named product
capability.

| Tutorial | Reader outcome | Current status |
|---|---|---|
| 1. From scoped goal to reviewed delivery | Run a small bug fix through definition, digest approval, worktree isolation, verification, and delivery. | Supported |
| 2. Choose between Addyosmani and AI-DLC | Compare the artifacts and judgment produced by two packs for the same bounded task. | Supported |
| 3. Use specialist profiles | Assign architecture, implementation, verification, and review profiles and inspect their structured handoffs. | Supported |
| 4. Recover a blocked verification card | Read evidence, comment, reassign, unblock, and confirm the same worktree and thread are reused. | Supported for retry/remediation without code rework |
| 5. Author a methodology pack | Pin external skills or a bundled adapter and validate a reusable stage mapping. | Supported |
| 6. Revise a rejected implementation safely | Replace the plan, invalidate approval, archive obsolete cards, and create a new graph revision. | Future: public plan-revision surface required |
| 7. Turn a delivery into a pull request | Review evidence, authorize commit/push separately, and preserve provenance in a PR. | Future: authorized integration surface required |
| 8. Trigger bounded work from issues or schedules | Apply trust filters, budgets, and approval policy before unattended start. | Future: trigger policy and unattended-run controls required |
| 9. Coordinate a cross-repository migration | Define ordered repository baselines, integration tests, and rollback. | Future: multi-repository workflow required |
| 10. Measure autonomous-development ROI | Export cycle time, cost, blocks, verification, review, and accepted outcomes. | Future: telemetry and reporting required |

## Future improvements worth addressing

The research and use cases above expose gaps that are valuable but should not be
hidden behind optimistic prose.

| Improvement | User need | Why it matters |
|---|---|---|
| Public plan revision and rework | Correct implementation after verification or review feedback without abandoning audit history. | This is the most immediate lifecycle gap; internal replacement logic exists but has no operator surface. |
| Authorized commit/PR handoff | Convert an accepted delivery into normal team review without giving workers uncontrolled push authority. | Current delivery stops before the collaboration surface most teams use. |
| Trigger admission policy | Start from trusted issue events or schedules with allowlists and explicit approval rules. | Unattended triggers increase prompt-injection and privilege risk. |
| Per-stage tool and network policy | Give each profile only the capabilities needed for its phase. | Pack skills constrain guidance, not host permissions. |
| Runtime budgets and loop limits | Bound elapsed time, retries, model spend, and verification attempts. | Long-running and parallel agents make cost and stalled work hard to see. |
| Multi-repository workflows | Coordinate API/client, service/infrastructure, or migration changes. | One repository and baseline are insufficient for common platform work. |
| Conflict-aware parallel workflows | Detect overlapping changed paths or stale baselines before two deliveries diverge. | Detached worktrees isolate execution but do not solve later integration conflicts. |
| Pack overlays or parameterized variants | Experiment with a stage skill while retaining provenance and reproducibility. | Today the choice is an entire existing pack or a newly authored pack. |
| Stronger skill supply-chain verification | Verify publisher signatures in addition to Git revisions and directory hashes. | Digests prove content identity, not publisher identity. |
| Outcome telemetry | Compare packs, profiles, and task classes using accepted-change metrics. | Evidence exists per workflow but is not aggregated into operational learning. |
| Additional approval gates | Require explicit human decisions before sensitive verification, integration, or release actions. | One pre-implementation gate is too coarse for some regulated or high-risk work. |

## Research sources

- [GitHub: About Copilot cloud agent](https://docs.github.com/copilot/concepts/agents/cloud-agent/about-cloud-agent) — common coding-agent tasks, isolated environments, specialization, limitations, and usage costs.
- [GitHub: Best practices for agent tasks](https://docs.github.com/copilot/how-tos/agents/copilot-coding-agent/best-practices-for-using-copilot-to-work-on-tasks) — task selection, acceptance criteria, repository instructions, and environment setup.
- [GitHub: Risks and mitigations](https://docs.github.com/enterprise-cloud@latest/copilot/concepts/agents/cloud-agent/risks-and-mitigations) — branch restrictions, credentials, prompt injection, auditability, and required human review.
- [OpenAI: Introducing Codex](https://openai.com/index/introducing-codex/) — isolated tasks, verifiable terminal evidence, testing, and repository instructions.
- [OpenAI: Harness engineering](https://openai.com/index/harness-engineering/) — repository legibility, worktree-local environments, feedback loops, documentation, and technical-debt control.
- [Anthropic: Measuring agent autonomy in practice](https://www.anthropic.com/research/measuring-agent-autonomy) — longer autonomous runs, changing oversight behavior, interruptions, and agent-initiated clarification.
- [OWASP: Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) — minimum functionality, permissions, autonomy, complete mediation, and human approval.
- [METR: 2026 developer-productivity experiment update](https://metr.org/blog/2026-02-24-uplift-update/) — task-selection effects, concurrent-agent measurement problems, and uncertainty around universal speedup claims.

## Daidala references

- Pack schema and skill providers: [Workflow-pack reference](03-pack-reference.md)
- Shipped stage mappings: [Pack adapters](09-pack-adapters.md)
- Worker artifacts and handoffs: [Lifecycle stages](05-lifecycle-stages.md)
- Recovery commands: [Operator runbook](07-runbook.md#recovery)
- Trust boundary: [Security](06-security.md)
- Host integration: [Hermes integration](08-hermes-integration.md)
