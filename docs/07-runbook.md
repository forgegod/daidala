# Daidala operator runbook

Daidala is operated through the native `hermes daidala` command. The
standalone `daidala` executable is the diagnostics-compatible form of the
same parser and handlers; it does not run a second agent or service.

## Install and enable

Supported hosts are exact Hermes v0.18.2, v0.19.0, and v0.20.0 releases within
the bounded pack range `>=0.18.2,<0.21.0`.

```bash
hermes plugins install forgegod/daidala --enable
hermes plugins list
```

Run all commands under the Hermes profile that owns the workflow. Profile
selection is a Hermes concern; Daidala resolves the active profile through
Hermes' home path and never writes a global fallback.

## Initialize

Initialization is dry-run by default:

```bash
hermes daidala init
hermes daidala init --apply --preview-digest <preview-digest> --confirm
```

The applied command requires the fresh digest printed by the dry run and literal
confirmation. It creates the profile-local `daidala/policy-ledger.sqlite3`
schema. Repeating it with a fresh preview is safe and reports a no-op. The dry
run prints the target path and does not create directories or files.

## Register a GitHub repository

Registration is preview-first and writes only after the selected controller
profile is resolved by Hermes. The selected profile must already have
`repository-registration-defaults.yaml`; see
[Configure registration defaults](#configure-registration-defaults).

```bash
daidala project register --github-url https://github.com/acme/payments-service \
  --profile controller
daidala project register --github-url https://github.com/acme/payments-service \
  --profile controller --apply --expected-preview-digest <preview-digest> \
  --confirm register-repository
```

Preview validates the canonical GitHub identity and committed project manifest,
then reports safe readiness, release flags, and the two proposed non-secret
profile-local records. Apply repeats that inspection and rejects stale digests.
It does not accept or store a token, create a checkout or GitHub Project, commit,
push, publish, or grant delivery authority. In the dashboard use **Config →
GitHub Repositories**: every Hermes profile is listed with its registered
repository, slug, board state, and GitHub Project link state. Inspect the
preview, confirm the named board bind/create action, then register.

### Project ID and GitHub Project

`project_id` is Daidala's stable identifier for the repository. It is a
lowercase slug declared in the repository's committed `.daidala/project.yaml`,
not a GitHub Project. Daidala uses it to identify the registration and name its
profile-local records under `$HERMES_HOME/projects/<project-id>/`.

For a repository that already has `.daidala/project.yaml`, the maintainer who
authored that committed policy chose the ID. For a repository classified as
`needs-bootstrap`, Daidala derives the ID from the canonical GitHub
`owner/repository` name during the bootstrap preview: it lowercases the name,
changes periods and underscores to hyphens, and collapses repeated hyphens. A
confirmed bootstrap writes the derived ID only on the bootstrap branch; it
becomes active only after a maintainer reviews and merges the pull request. A
maintainer who writes the manifest manually must choose a valid slug instead.

Treat the committed ID as a stable primary identifier, not a routine setting.
After registration, do not change it: Daidala provides no supported ID-migration
command or dashboard control. A GitHub Project is separate and optional.
Registration neither requires nor creates one; a separately configured GitHub
Project link is presentation/intake metadata, not the repository identity.

### Bootstrap policy for a non-Daidala repository

If inspect classifies the repository as `needs-bootstrap` (no committed
`.daidala/project.yaml`), the dashboard inspect control becomes **Apply
default policy**. Confirm the preview, then publish conservative policy on
branch `chore/daidala-bootstrap-project-policy` first:

```bash
daidala project bootstrap --github-url https://github.com/acme/site \
  --profile controller
daidala project bootstrap --github-url https://github.com/acme/site \
  --profile controller --apply --expected-preview-digest <preview-digest> \
  --confirm bootstrap-repository
```

Bootstrap uses host `gh` authentication, never updates the default branch, and
never writes registration records. Confirmed apply opens one pull request on
the inspected repository. The dashboard keeps that PR link on the inspected
row after a Hermes restart until the repository is registered. Merge the PR,
then run `project register` again.

### Configure registration defaults

Inspect and register read profile-local
`repository-registration-defaults.yaml` from the selected Hermes profile data
root (`$HERMES_HOME/repository-registration-defaults.yaml`). That file is
profile authority, not repository policy. A GitHub URL and committed
`.daidala/project.yaml` cannot supply it. Config → GitHub Repositories
explains each field in the defaults wizard so operators can complete it
without opening this section first.

The file holds aliases, environment-variable *names*, maintainers, an attended
notification destination, evaluator posture, and cycle limits. It never holds
GitHub token values. GitHub tokens stay in the process environment named by
those variables. Config → GitHub Repositories shows the same field help.

#### Configured GitHub access rights

This group names already-configured GitHub access. Daidala does not create a
GitHub token or grant rights. Create the GitHub token and its access rights
first, store the value in the profile process environment, then enter only the
alias and environment-variable name here.

- **Intake alias.** Logical name for the already-configured read-only GitHub
  access used to list and claim issues. Lowercase slug such as
  `github-read-issues`. Must differ from the findings alias. This is a label,
  not the GitHub token.
- **Intake environment variable.** Name of the process environment variable
  that already holds the intake GitHub token, such as
  `EXAMPLE_GITHUB_INTAKE_TOKEN`. Uppercase letters, digits, and underscores
  only. Never `GH_TOKEN`, and never paste the GitHub token itself. Use a
  classic personal access token, not a fine-grained token. Mandatory classic
  scopes are `read:project` and `read:org`. Leave `repo`, `public_repo`,
  project write, workflow, package, administration, and deletion unselected.
  Fine-grained tokens cannot access user-owned GitHub Projects.
- **Findings alias.** Logical name for the already-configured write GitHub
  access used to open or update finding issues. Use a different lowercase slug
  such as `github-write-issues` so read and write stay separate.
- **Findings environment variable.** Name of the process environment variable
  that already holds the findings GitHub token. It must differ from the intake
  variable. Same uppercase name rules; never `GH_TOKEN` or the GitHub token
  value. Use a fine-grained personal access token, the current GitHub token
  type, restricted to the target repository. Mandatory repository permissions
  are Metadata read and Issues read and write. Leave Contents, Administration,
  Pull requests, Actions, Workflows, Deployments, and other permissions at No
  access.

The executable creation steps for the self-improvement controller live in
[Configure GitHub operator and runtime credentials](16-self-improvement-setup.md#3-configure-github-operator-and-runtime-credentials).

#### Approval

- **Maintainers.** Who may admit work for repositories registered from this
  profile. One to 32 unique identities. Use the same identity the gateway will
  present, such as `example-operator`.

#### Attended notifications

- **Notification target.** A local nickname for the attended destination, such
  as `attended-example`. Lowercase slug. Notification receipts must match this
  name.
- **Notification destination.** Where Hermes sends attended reviews. Must be
  an explicit non-home target such as `telegram:<chat-id>` or
  `telegram:<chat-id>:<thread-id>`. Do not use `home`. The adapter is
  `hermes-gateway`.

#### Evaluator

- Backend must be `restricted-container` and network `denied-by-default`.
  The wizard does not ask for these values because they are fixed.

#### Cycle limits

These values are copied onto every new registration as this profile's
declared budget. They are not live runtime gates beyond that write.

- **Active cycles.** v1 requires exactly `1`.
- **Goal turns.** Integer from 1 to 100. `12` is the recommended start.
- **Delegated workers.** Integer from 0 to 9. `3` is the recommended start.
- **Research query batches.** Integer from 0 to 10. `3` is the recommended start.
- **Extracted sources.** Integer from 0 to 20. `3` is the recommended start.
- **Wall-clock seconds.** Integer from 60 to 86400. `3600` is one hour.

Write the file by hand and `chmod 600`, or use the CLI or Config wizard
below. If the profile already has a registered project, `--seed` or **Seed
from existing registration** copies the non-secret aliases, destination,
evaluator, and limits from that project's `registration.yaml` and
`credential-bindings.yaml`.

Example (synthetic values only):

```yaml
schema: daidala.repository-registration-defaults/v1
credentials:
  intake:
    alias: github-read-issues
    resolver: environment
    environment_variable: EXAMPLE_GITHUB_INTAKE_TOKEN
  findings:
    alias: github-write-issues
    resolver: environment
    environment_variable: EXAMPLE_GITHUB_FINDINGS_TOKEN
approval:
  maintainers:
    - example-operator
notifications:
  adapter: hermes-gateway
  target: attended-example
  destination: telegram:-1000000000000:1
evaluator:
  backend: restricted-container
  network: denied-by-default
limits:
  active_cycles: 1
  goal_turns: 12
  delegated_workers: 3
  research_query_batches: 3
  extracted_sources: 3
  wall_clock_seconds: 3600
```

After the file exists, inspect again. A repository that already has committed
`.daidala/project.yaml` becomes a registration preview. A repository that
lacks that file is classified `needs-bootstrap` and does not require this
defaults file until you register.

Validate or write the file from the CLI or Config → GitHub Repositories:

```bash
daidala project defaults --profile controller
daidala project defaults --profile controller --seed
daidala project defaults --profile controller --from-file ./repository-registration-defaults.yaml
daidala project defaults --profile controller --from-file ./repository-registration-defaults.yaml \
  --apply --expected-preview-digest <preview-digest> --confirm write-registration-defaults
```

Dry-run prints a path-free validity report and digest. Apply writes mode `0600`
`$HERMES_HOME/repository-registration-defaults.yaml`. `--seed` copies aliases,
destination, evaluator, and limits from the profile's single existing
registration; it does not invent missing values. A missing or invalid file still
blocks `project register`.

## Diagnose prerequisites

```bash
hermes daidala doctor --project-manifest /absolute/repository/.daidala/project.yaml
```

`doctor` emits the strict self-improvement prerequisite report. Add
`--registration /profile/projects/<project-id>/registration.yaml` to bind the
trusted profile-local authority and `--live` to run bounded GitHub, gateway, and
container availability probes. Without `--live`, those checks are `not-run` and
the command exits `2`. Exit `0` means every documented check passed; exit `1`
means invalid input or checker failure. The command never fixes setup state.

Inspect and install pack dependencies explicitly:

```bash
hermes daidala packs list
hermes daidala packs validate addyosmani
hermes daidala packs install addyosmani
hermes daidala packs install addyosmani --apply
hermes daidala packs check addyosmani
```

Installation is also dry-run by default. Review every proposed `hermes skills
install` command before using `--apply`. Recursive installation is refused by
the verified Hermes baseline. `revision_mismatches` are warnings: they do not
block `--apply`, `packs check`, or workflow start. A missing or disabled exact
skill name remains blocking.

In the dashboard, **Config → Packs** renders bounded literal `SKILL.md` text only
for bundled or installed skills. Select a declaration to move keyboard focus and
the viewport to its information panel, open its exact source link, and use its
applicable **Install skill**, **Enable skill**, or **Disable skill** action. A
digest mismatch is shown there as a warning while the installed skill remains
available. **Install all**, **Enable all**, and **Disable all** target every
applicable declared skill in the pack. Review the affected names and preview
digest, tick the confirmation box, then apply; Daidala rejects stale previews and
verifies installation presence or enabled state afterward. Disable is a
reversible update to `skills.disabled` for the active profile, not an uninstall.

Uninstalled Addyosmani skills remain labeled `installation required` with their
exact install targets. Installed but disabled skills are also not ready. An
installed digest mismatch yields `ready with warnings` rather than a blocker.
Start workflow keeps a blocked pack selectable for inspection but disables
preview/start until every exact skill name is installed and enabled.

## Start and resume a workflow

In the dashboard, select exactly one workspace mode. **Registered GitHub
repository** lists every registered repository in the Hermes installation and
derives that tuple's board and checkout server-side. Only a bound board is
selectable; uniqueness or bind failures stay listed with a reason and
conclusion. Start shows the working directory for the chosen workspace.
The repository profile owns the registration. Worker profile default assigns
who runs the cards; a mismatch is allowed and later stages fail if those
workers cannot use the working directory.
**Existing unregistered
repository** exposes only unbound boards whose configured workdir is a clean Git
root. **Initialize local project** accepts only a slug and board display name,
then previews the derived directory, default `.daidala` policy, initial commit,
and unbound board; it creates no GitHub repository or Project link.

Start explicitly on an existing named board. One default profile is sufficient;
override only stages that need a different profile:

```bash
hermes daidala start /absolute/path/to/repo "Implement the requested change" \
  --board project-board \
  --default-profile engineer \
  --stage-profile define=architect \
  --stage-profile review=reviewer \
  --pack addyosmani \
  --workflow-id stable-workflow-id
```

Do not use `--profile`; Hermes consumes it as a host-level option before the
plugin command parser receives it. Daidala expands and validates the complete
stage map, then creates `define → plan`. Observe progress through normal Kanban
surfaces and use combined diagnostics when needed:

```bash
hermes kanban --board project-board watch
hermes daidala status stable-workflow-id
```

The gateway's Kanban dispatcher executes ready cards. Start and Workflows
readiness require the selected worker profile gateway to be running
(`hermes -p <worker> gateway start`) and refuse a live card whose assignee
does not match the workflow-bound stage profile. When a Ready card's assigned
gateway is stopped or unavailable, its Workflows card names the stage/card,
profile, gateway state, and status/start commands. That warning is read-only:
it does not change workflow state or start a gateway. The start command creates
the graph; it does not start a second scheduler, daemon, or nested agent.

## Start a Git-pinned plan phase

`start-from-plan` admits exactly one pending phase from a clean, full Git
revision. The plan path is repository-relative; Daidala reads its blob from the
named commit, not mutable checkout bytes. Preview first:

```bash
hermes daidala start-from-plan /absolute/path/to/repo \
  --plan-path docs/plans/P0440-example.md \
  --source-revision <full-commit-a> --phase 0 \
  --board project-board --default-profile engineer \
  --pack addyosmani --workflow-id example-phase-0
```

Apply only with the returned digest:

```bash
hermes daidala start-from-plan /absolute/path/to/repo \
  --plan-path docs/plans/P0440-example.md \
  --source-revision <full-commit-a> --phase 0 \
  --board project-board --default-profile engineer \
  --pack addyosmani --workflow-id example-phase-0 --apply \
  --expected-preview-digest <preview-digest>
```

The imported workflow has no synthetic `define` or `plan` card. Its dashboard
summary and approval recommendation show the Git-pinned source revision, Plan
ID, phase, packet digest, and `verified` packet state without source paths or
bytes. Approval binds that packet as well as the current plan and constraint
tuple.

Accepted review can be delivered only through the separately previewed,
explicitly confirmed `daidala/<workflow-id>` branch transaction described below.
If an operator chooses to continue the Git-pinned phase sequence, they still
create and authorize the next direct child checkpoint containing the accepted
changes and allowed `done (daidala:<workflow-id>:<delivery-digest>)`
phase-status projection. Then admit the next pending phase from that child commit
with a new workflow ID and `--predecessor-workflow-id <prior-workflow-id>`.
The prior approval cannot authorize that new packet or baseline.

## Review exact artifacts

List ledger-owned artifacts and select one exact opaque artifact ID. JSON list
output contains metadata only; it never includes artifact content or labels one
revision as `latest`:

```bash
hermes daidala artifacts list <workflow-id> --json
hermes daidala artifacts show <workflow-id> <artifact-id>
```

`show` writes only digest-verified UTF-8 text within the 1 MiB document bound.
For binary or larger artifacts, export verified bytes to a destination whose
parent directory already exists:

```bash
hermes daidala artifacts export <workflow-id> <artifact-id> \
  --output /operator/selected/artifact.bin
```

Export creates a mode-`0600` regular file atomically and refuses an existing
destination unless `--overwrite` is present. The destination is never accepted
as an artifact read source.

Preview and apply a manual terminal-workflow archive, then inspect or restore
one exact archive ID:

```bash
hermes daidala curator archive <workflow-id>
hermes daidala curator archive <workflow-id> --apply \
  --expected-preview-digest <archive-preview-digest>
hermes daidala curator list-archived
hermes daidala curator restore <workflow-id> <archive-id>
hermes daidala curator restore <workflow-id> <archive-id> --apply \
  --expected-preview-digest <restore-preview-digest>
```

Archive apply verifies every member before removing matching active sources.
Artifact list/show/export continue to resolve the unchanged ledger identities
from that archive. Restore writes only below the derived profile-local recovery
root, does not rewrite the ledger path, and leaves the verified archive intact.

## Schedule artifact curation

Policy and scheduling are disabled until an operator previews and confirms
their exact identities. Configure the curator policy, then register one
controller profile:

```bash
hermes daidala curator configure --enabled \
  --stale-after-days 30 --archive-after-days 90
hermes daidala curator configure --enabled \
  --stale-after-days 30 --archive-after-days 90 --apply \
  --expected-state-digest <state-digest> \
  --confirm-policy-digest <policy-digest>
hermes daidala curator schedule setup "every 1d"
hermes daidala curator schedule setup "every 1d" --apply \
  --expected-preview-digest <preview-digest> \
  --confirm-controller-profile <controller-profile>
```

The preview binds the interval, curator policy digest, and exact installed Bash
launcher. Setup creates or updates one profile-local script-only/no-agent Hermes
Cron job and records the returned job ID. Repeating unchanged setup reuses that
job. Policy or script changes require a new preview. Inspect and remove only the
recorded job with:

```bash
hermes daidala curator schedule status
hermes daidala curator schedule remove
hermes daidala curator schedule remove --apply \
  --expected-preview-digest <remove-preview-digest> \
  --confirm-controller-profile <controller-profile>
```

The gateway scheduler must be running. An idle or disabled-policy tick is
silent and performs no curator mutation; failures remain classified Cron runs.

## Approve the exact plan

Approval remains bound to the SHA-256 digest recorded on the current plan
artifact:

```bash
hermes daidala approve <workflow-id> <64-character-plan-digest>
```

Do not copy a digest from an older plan revision. A mismatch fails without
authorizing work. Generic `hermes kanban unblock` is not approval. Successful
approval records the ledger gate and creates
`implement → verify → review` in one persistent worktree. Automated review does
not create `deliver`.

## Review disposition

Inspect the bounded current packet before taking attended action:

```bash
hermes daidala review show <workflow-id>
```

The response supplies the board, review card ID, exact evidence tuple, current
disposition, allowed actions, and any pending successor packet. The dashboard
workflow detail exposes the same authority through a source-bound evidence panel:
preview the selected disposition, inspect its fixed consequences and successor
packet, check the literal confirmation, then apply. The browser never selects an
actor, card, artifact path, worktree path, or revision identity.

Every rationale file must be direct, regular, non-symlinked, non-empty UTF-8 and
at most 4096 bytes. The file path is input only and is never persisted.

For an accepted review with no blocking findings, preview and then apply exact
delivery acceptance:

```bash
printf '%s\n' 'Accepted after inspecting the exact review evidence.' > review-rationale.txt
hermes daidala review decide <workflow-id> accept-delivery \
  --rationale-file ./review-rationale.txt
hermes daidala review decide <workflow-id> accept-delivery \
  --rationale-file ./review-rationale.txt --apply \
  --expected-review-digest <review-digest> \
  --expected-preview-digest <preview-digest>
```

Preview is non-mutating. Apply re-reads the current tuple; stale review or
preview digests fail before mutation. Successful acceptance creates exactly one
`deliver` card. Blocking findings cannot be overridden.

## Reviewed branch delivery

After accepted review creates the activated Deliver card, preview the exact
reviewed diff, branch, release policy, and credential readiness. Delivery never
accepts a token, remote, branch, worktree path, or changed path from the
operator:

```bash
hermes daidala deliver <workflow-id>
hermes daidala deliver <workflow-id> --apply \
  --expected-preview-digest <preview-digest> --confirm
```

The preview is non-mutating. Apply repeats every check and commits only the
captured reviewed paths to `daidala/<workflow-id>`, then pushes only that exact
commit and verifies the remote ref. It fails closed for a missing explicit
`github-repository-delivery` credential binding/value, false committed release
flags, stale review or diff evidence, changed registration/remote, an existing
conflicting branch, or a stale preview. A valid retry resumes the same recorded
commit/push transaction; do not create or push the branch manually. The checkout
must still use its exact registered remote. Git transport uses the canonical
GitHub HTTPS endpoint derived from the same registration (rather than reusing an
SSH checkout URL) so the dedicated PAT remains isolated in temporary askpass
state. Before retry recovery releases an owned worktree, Daidala reads the live
Deliver card's single completed run and requires its exact non-secret
`daidala.delivery/v1` branch and commit receipt; a done card with unrelated or
missing run metadata remains blocked for attended investigation.

On success Daidala records the branch/commit receipt, completes the Deliver card,
and releases only its owned worktree. It does not open a pull request, merge,
touch a default branch, create a release, or publish. In the dashboard open the
workflow detail, use **Preview branch delivery**, inspect the path-free evidence,
tick the literal confirmation, and choose **Confirm commit and push branch**.

If reviewer judgment is disputed but captured code need not change, use the
board and review-card ID from `review show`:

```bash
hermes kanban --board <board> comment <review-card-id> "Challenge: <reason>"
hermes kanban --board <board> unblock <review-card-id> --reason "Re-review requested"
```

If code, verification scope, or implementation approach must change, preview
and apply revision instead:

```bash
printf '%s\n' 'Address the findings and rerun the named verification.' > revision-feedback.txt
hermes daidala review decide <workflow-id> request-revision \
  --rationale-file ./revision-feedback.txt
hermes daidala review decide <workflow-id> request-revision \
  --rationale-file ./revision-feedback.txt --apply \
  --expected-review-digest <review-digest> \
  --expected-preview-digest <preview-digest>
```

Apply preserves the rejected plan, implementation, verification, review,
disposition, and card history; archives only recorded current post-gate cards;
releases only the owned worktree; and returns the new plan revision and Plan card
ID. Inspect the card, wait for `plan-N/plan.md`, inspect that plan, and apply its
new digest through the normal approval gate:

```bash
hermes kanban --board <board> show <plan-card-id> --json
hermes daidala status <workflow-id>
hermes daidala approve <workflow-id> <new-plan-digest>
```

No new worktree or implementation card exists before fresh approval. There is no
direct phase-rewind command.

To reject the workflow at the review gate, use the same preview/apply sequence
with `reject-workflow`:

```bash
printf '%s\n' 'Rejecting this workflow after inspecting its exact evidence.' > rejection-rationale.txt
hermes daidala review decide <workflow-id> reject-workflow \
  --rationale-file ./rejection-rationale.txt
hermes daidala review decide <workflow-id> reject-workflow \
  --rationale-file ./rejection-rationale.txt --apply \
  --expected-review-digest <review-digest> \
  --expected-preview-digest <preview-digest>
```

## Cancel

Cancellation requires an audit reason:

```bash
hermes daidala cancel <workflow-id> "Superseded by a different change"
```

Cancellation comments and archives the workflow's cards through public Hermes
operations and cleans only its Daidala-owned worktree. The policy and artifact
ledger remains available for diagnostics.

## Recovery

The optional `/daidala` view labels unavailable Kanban state instead of using a
cached status. Use **Refresh** after restoring the gateway or host CLI. Setup and
constraint previews are safe to repeat; confirmed starts are idempotent, while a
stale constraint digest must be previewed again before replacement.

Hermes Kanban owns retry and recovery:

1. Inspect the named board and card with `hermes kanban --board <slug> show <id>`.
2. Read the worker comment, run metadata, and exact block reason.
3. Correct missing profile skills or capability prerequisites without mutating
   another profile's store implicitly.
4. Comment with the decision or remediation, reassign when necessary, and use
   `hermes kanban --board <slug> unblock <id> --reason "..."`.
5. The dispatcher respawns the card with its full thread and preserved absolute
   worktree. Never fabricate replacement evidence.

Artifact-write, archive, worktree-release, and successor Plan-card failures in a
confirmed revision request are retryable with the same exact review and preview
digests. The persisted request and progress markers prevent duplicate authority;
do not cancel or manually rewind merely because one host mutation failed.

A failed branch-delivery retry must use the same displayed preview digest only
when the review and recorded evidence remain current. The delivery service
revalidates the branch, commit, and remote ref; do not reset the owned worktree,
force-push, or manually create the Daidala branch.

Legacy ledgers without structured review fields remain readable, but `review
show`, disposition, and delivery fail closed. Never infer acceptance from a
historical `review.md`. Resume the current review worker so it records supported
structured evidence when that graph remains active; otherwise cancel and start a
new workflow under the current contract.

## Dashboard equivalence

The optional **Daidala → Config → Runbook** panel links each runbook operation
to its bounded browser surface: initialization preview/apply and prerequisite
diagnosis, pack inspection, workflow supervision/resume, exact-plan approval,
review disposition, branch-delivery preview/confirmation, and cancellation.
Browser workflow selection only reopens an existing workflow for read-only
polling; it never starts another graph or scheduler.

Install, enable, upgrade, plugin removal, gateway lifecycle, and standalone
diagnostics remain native CLI operations. The dashboard renders their exact
commands as guidance only and has no plugin-management, restart, or generic
command-dispatch route.

## Upgrade

```bash
hermes plugins update daidala
hermes daidala doctor --project-manifest /absolute/repository/.daidala/project.yaml
hermes daidala packs check addyosmani
```

Do not widen the documented Hermes compatibility range based only on a successful
install. A new host version requires the repository's plugin-load, CLI, test,
build, and clean-install probes.

## Standalone diagnostics

The following forms are intentionally equivalent and return the same JSON and
exit code:

```bash
hermes daidala status <workflow-id>
daidala status <workflow-id>
hermes daidala review show <workflow-id>
daidala review show <workflow-id>
hermes daidala deliver <workflow-id>
daidala deliver <workflow-id>
hermes daidala artifacts list <workflow-id> --json
daidala artifacts list <workflow-id> --json
hermes daidala artifacts show <workflow-id> <artifact-id>
daidala artifacts show <workflow-id> <artifact-id>
hermes daidala artifacts export <workflow-id> <artifact-id> --output <path>
daidala artifacts export <workflow-id> <artifact-id> --output <path>
```

Replacing the `hermes daidala` prefix with `daidala` in the `review decide` and
`deliver` preview/apply examples above is also equivalent; both forms share one
parser and dispatch path.

Use the native form operationally. The standalone executable exists for package
smoke tests and diagnostics, not as a separate orchestration runtime.
