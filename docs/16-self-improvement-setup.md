# Self-improvement environment prerequisites

## Purpose

This checklist prepares the one supported Daidala self-improvement dogfood
environment before a live cycle is admitted. Complete every required row and
retain the command output as redacted setup evidence. A repository test cannot
replace a failed host probe.

This document does not authorize a cycle, implementation, retention, commit,
push, publication, release, or runtime promotion. Those remain separate gates
in the [self-improvement flow](15-self-improvement.md).

This guide is the normative source of truth for the Daidala dogfood
prerequisites and their remediation. The implemented read-only CLI checker
mirrors the stable check IDs in the ready-to-admit table and reports omissions;
it cannot add, weaken, waive, or silently repair a prerequisite. A passing
report is evidence for human review, not setup approval or cycle approval.

Authoritative external references:

- [Hermes profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles)
- [Hermes plugins](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)
- [Hermes Kanban](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban)
- [Hermes messaging gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/)
- [GitHub CLI authentication refresh](https://cli.github.com/manual/gh_auth_refresh)
- [GitHub personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Fine-grained token permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)
- [Docker Desktop WSL integration](https://docs.docker.com/desktop/features/wsl/)

## Fixed instance identity

| Concern | Required value |
|---|---|
| Repository | `forgegod/daidala` |
| Checkout | `/home/raphael/src/rb/daidala` |
| Git remote | `git@github.com:forgegod/daidala.git` |
| Project ID | `forgegod-daidala` |
| Controller profile | `daidala-self-improvement` |
| Kanban board | `daidala-forgegod-daidala` |
| Notification alias | `attended-daidala` |
| Evaluator | `restricted-container` |
| Evaluator network | `denied-by-default` |
| Supported Hermes baseline | `v0.18.2` |
| Approved controller revision | `afe1805fca5e27edc2e70ac526a697e76d8890fb` |

The controller may carry model, issue, and notification credentials. A fresh
evaluator must not clone the controller profile or receive issue mutation,
notification, publication, release, or controller credentials.

## Current prerequisite state

This table is the current setup inventory. Only a clean, non-mutating
`daidala doctor --live` report can promote a prerequisite from inventory to
retained evidence.

| Prerequisite | State | Evidence |
|---|---|---|
| Hermes baseline | Pass | `Hermes Agent v0.18.2 (2026.7.7.2)` |
| Repository identity | Pass | Approved revision `afe1805fca5e27edc2e70ac526a697e76d8890fb` is synchronized across local `HEAD`, `origin/main`, and remote `main`. Run the final report only from a clean checkout. |
| Daidala development installation | Partial | The standalone `0.2.0` command exists in the checkout virtualenv, but the controller profile discovers no non-bundled Daidala plugin. |
| Controller plugin revision | Partial | Approved revision `afe1805fca5e27edc2e70ac526a697e76d8890fb` is synchronized, contains the evaluator implementation, and passes the repository gate. It is not installed in the controller profile. |
| Controller profile | Pass | `/home/raphael/.hermes/profiles/daidala-self-improvement` exists and the sticky profile remains `hermes-vc`. |
| Dedicated board | Blocked | Only the `default` board exists. |
| Restricted container | Partial | Docker client and server `29.6.1` are available and the built-in `none` network resolves, but no pinned evaluator image or isolation receipt exists. `SI-EVALUATOR` remains blocked. |
| GitHub runtime credentials | Partial | `GH_TOKEN_DAIDALA_READ_ISSUES` and `GH_TOKEN_DAIDALA_WRITE_ISSUES` are configured in the controller profile environment. Their non-secret alias bindings and retained capability evidence do not exist. |
| GitHub operator credential | Pass | `gh-vault run --name ghcli -- gh project list` succeeds, and `GH_TOKEN_DAIDALA_PROJECT_MGMT` is absent from the controller profile. Attended Project authority remains isolated in `gh-vault`. |
| GitHub Project | Partial | User-owned Project 1 exists at `https://github.com/users/forgegod/projects/1` with node ID `PVT_kwHOAAjENs4Bd2Xo`. It contains only the 13 default fields; the eight required Daidala fields and auto-add workflow are absent. |
| Attended notification | Partial | Telegram is configured as the controller profile's home platform and the profile gateway is running. No approved attended probe receipt is retained, so `SI-NOTIFICATION` remains blocked. |
| Self-improvement labels | Blocked | No `daidala-si:*` labels exist; mutation waits for the least-privilege credential gate. |
| Trusted runtime state | Blocked | `registration.yaml`, `credential-bindings.yaml`, and `prerequisite-evidence.json` do not exist for `forgegod-daidala`; no active cycle has been admitted. |

Do not admit UC-01 while any required row is blocked.

## Reproduction sequence

This file is the complete setup and configuration guide. Reproduce the instance
in this order; a later step must not be used to waive an earlier blocker.

| Step | Result | Mutation | Current state |
|---|---|---|---|
| 1 | Verify host and repository identity. | None. | Pass; repeat from the final clean checkout. |
| 2 | Verify Docker availability, then later produce evaluator isolation evidence. | The isolation probe creates a disposable container. | Docker available; receipt blocked. |
| 3 | Provision one attended operator credential and two least-privilege runtime credentials. | Vault and profile environment only. | Tokens configured; operator token isolated; binding and capability evidence incomplete. |
| 4 | Create the controller profile without changing the sticky profile. | Hermes profile. | Pass. |
| 5 | Install the selected detached Daidala revision. | Controller plugin directory. | Not started; separate setup approval required. |
| 6 | Create the dedicated Kanban board. | Hermes board. | Not started; separate setup approval required. |
| 7 | Configure and verify the attended gateway target. | Profile gateway/home channel. | Gateway running; receipt blocked. |
| 8 | Create labels and the user-owned GitHub Project. | GitHub Issues and Projects. | Project created; labels, required fields, and auto-add workflow pending. |
| 9 | Materialize trusted non-secret registration, bindings, and receipts. | Profile-local project files. | Not started. |
| 10 | Run the read-only live prerequisite checker from a clean checkout. | None. | Blocked by Steps 5-9. |
| 11 | Admit UC-01 manually. | GitHub issue, board, evaluator, and cycle artifacts. | Deliberately deferred until every `SI-*` check passes. |

The operator owns browser authorization, credential creation, attended-channel
confirmation, setup approval, and later cycle approval. The agent may select a
verified revision and perform approved mechanical setup, but it must not infer
credentials, invent receipts, or silently start UC-01.

## 1. Run the non-mutating preflight

These commands were exercised against Hermes v0.18.2 and the current checkout:

```bash
hermes --version
hermes profile list
hermes profile show daidala-self-improvement
hermes kanban boards list
hermes -p daidala-self-improvement gateway status
hermes -p daidala-self-improvement plugins list --plain --no-bundled

docker version --format '{{.Client.Version}}|{{.Server.Version}}'

gh-vault list
gh-vault run --name ghcli -- gh api user --jq .login
gh-vault run --name ghcli -- gh repo view forgegod/daidala \
  --json nameWithOwner,url,viewerPermission,hasIssuesEnabled
gh-vault run --name ghcli -- \
  gh project list --owner @me --limit 100 --format json
```

Expected failures are actionable blockers, not values to copy into the trusted
registration. Never copy token strings, connection strings, or credential file
contents into setup evidence.

## 2. Enable the restricted container boundary

On Windows, open Docker Desktop:

1. Open **Settings**.
2. Open **Resources > WSL Integration**.
3. Enable integration for the WSL distro running this checkout.
4. Apply and restart Docker Desktop.

Verify from this WSL shell:

```bash
docker version --format '{{.Client.Version}}|{{.Server.Version}}'
docker network inspect none --format '{{.Name}}|{{.Driver}}'
```

The actual evaluator probe must later use a pinned evaluator image,
`--network none`, a fresh home, explicit mounts, and no controller credential
mounts. Do not pull an arbitrary image merely to make this prerequisite pass.
If Docker cannot run from WSL, stop; do not replace `restricted-container` with
the local backend.

Docker client/server `29.6.1` and the built-in `none` network are available.
This satisfies Docker availability only. It does not
prove that the evaluator excludes controller credentials, rejects disallowed
mounts, binds the approved image digest, or enforces the document limits.

## 3. Configure GitHub operator and runtime credentials

This setup uses three distinct credentials: one attended operator Project
credential, one read-only intake credential, and one issue-write findings
credential. The operator credential is stored in `gh-vault` profile `ghcli`.
The two runtime values are configured in the controller profile environment;
their non-secret Daidala bindings and capability evidence remain to be created.

The trusted registration names runtime aliases only. It never contains token
values, and the implementation must verify alias capability without exposing a
credential.

These capabilities are properties of runtime credentials, not settings on the
GitHub Project. The Project contains fields and items; it does not hold API
permissions or Daidala aliases.

Required runtime credential capabilities:

| Alias | Allowed | Denied |
|---|---|---|
| `github-daidala-read-issues` | Read repository metadata, labels, issues, comments, and Project fields. | Create/edit issues, repository contents, administration, merge, release, deployment. |
| `github-daidala-write-issues` | Read metadata and create/update labeled findings. | Repository contents, administration, merge, release, deployment. |

For the current user-owned `forgegod` Project, GitHub documents an important
limitation: fine-grained personal access tokens cannot access Projects owned by
a user account. The minimal practical split is therefore:

- `github-daidala-read-issues`: a classic personal access token with only
  `read:project`; public issue, label, comment, and repository metadata remain
  readable without a repository-write scope;
- `github-daidala-write-issues`: a fine-grained personal access token whose
  resource owner is `forgegod`, repository selection is only `daidala`, and
  repository permissions are `Metadata: read` and `Issues: read and write`.

### 3.1 Configure the operator Project credential
The operator credential creates and configures the Project. It is not used by
the unattended controller and is not one of the two runtime aliases.

For a fresh machine, authorize a token with `read:project`, `project`,
`read:org`, and `read:discussion`, then store it without placing the value on a
command line:

```bash
read -rsp 'Operator GitHub token: ' token; printf '\n'
printf '%s' "$token" | gh-vault set ghcli --stdin \
  --note 'Attended Daidala Project setup only'
unset token
```

If `gh` already owns the token, `gh auth refresh --hostname github.com
--scopes read:project,project,read:org,read:discussion` is the supported
interactive alternative, followed by
`gh auth token | gh-vault set ghcli --stdin`. Do not copy the resulting token
into the controller profile. Let `gh-vault set` inspect the token; a manual
scope declaration is metadata, not capability proof.

Verify through the bounded child-command surface:

```bash
gh-vault run --name ghcli -- gh api user --jq .login
gh-vault run --name ghcli -- \
  gh project list --owner @me --limit 100 --format json
```

The login must be `forgegod`. The Project command must return JSON without an
authorization error; an empty list means access works but setup has not created
the Project. `gh-vault run` injects the token only into the child process.

`GH_TOKEN_DAIDALA_PROJECT_MGMT` is not consumed by Daidala. If it exists in the
controller profile `.env`, remove that entire variable there after confirming
`gh-vault` access. Keep attended Project authority in `gh-vault`, outside the
unattended controller.

### 3.2 Create `github-daidala-read-issues`

GitHub currently documents that fine-grained personal access tokens cannot
access Projects owned by a user account. Use a narrowly scoped classic token for
this read-only alias:

1. Open [Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens).
2. Select **Generate new token > Generate new token (classic)**.
3. Name it `Daidala issue intake` and select a short expiration.
4. Select only **`read:project`**.
5. Leave `repo`, `public_repo`, `project`, `workflow`, package, administration,
   and deletion scopes unselected.
6. Generate the token and save it immediately in your own password manager or
   organization vault. Use `github-daidala-read-issues` as the entry name.
7. Close the GitHub page after confirming that the password manager or vault
   contains the value. GitHub will not show the token again.

The alias is a Daidala name, not an object created in GitHub. Public repository
metadata, issues, labels, and comments remain readable without a repository
scope; `read:project` adds read access to the user-owned Project fields.

To probe the token without adding it to shell history, run this manually in an
attended shell:

```bash
read -rsp 'Read token: ' DAIDALA_READ_TOKEN; printf '\n'
GH_TOKEN="$DAIDALA_READ_TOKEN" gh project list \
  --owner forgegod --limit 100 --format json
GH_TOKEN="$DAIDALA_READ_TOKEN" gh issue list \
  --repo forgegod/daidala --limit 1
unset DAIDALA_READ_TOKEN
```

Both reads must succeed. Do not test denied mutation by attempting to alter a
real issue or Project.

### 3.3 Create `github-daidala-write-issues`

Use a fine-grained token restricted to one repository for finding publication:

1. Open [Developer settings > Personal access tokens > Fine-grained tokens](https://github.com/settings/personal-access-tokens).
2. Select **Generate new token**.
3. Name it `Daidala finding publisher`, add a short expiration, and select
   `forgegod` as the resource owner.
4. Under **Repository access**, select **Only select repositories**, then select
   only `daidala`.
5. Under **Repository permissions**, set **Issues** to **Read and write**.
6. Keep **Metadata** at its automatic **Read-only** value.
7. Leave Contents, Administration, Pull requests, Actions, Workflows,
   Deployments, Environments, Pages, Secrets, Variables, and other permissions
   at **No access**.
8. Generate the token and save it immediately in your own password manager or
   organization vault. Use `github-daidala-write-issues` as the entry name.

Verify its read half without exposing the token:

```bash
read -rsp 'Findings token: ' DAIDALA_FINDINGS_TOKEN; printf '\n'
GH_TOKEN="$DAIDALA_FINDINGS_TOKEN" gh issue list \
  --repo forgegod/daidala --limit 1
unset DAIDALA_FINDINGS_TOKEN
```

Do not verify write access by creating a disposable issue: GitHub issues cannot
be deleted through the normal workflow and the probe would leave live state.
The first write probe belongs to the separately approved controlled issue and
must retain its returned issue ID and URL as setup evidence.

Store only the two runtime values in the controller profile environment. If the
profile does not exist on a fresh machine, complete Section 4 first and return
here:

```bash
profile_env="$(hermes -p daidala-self-improvement config env-path)"
chmod 600 "$profile_env"
"${EDITOR:-nano}" "$profile_env"
```

Add these two assignments with their real values:

```dotenv
GH_TOKEN_DAIDALA_READ_ISSUES=<read-only-intake-token>
GH_TOKEN_DAIDALA_WRITE_ISSUES=<issue-write-findings-token>
```

Remove any `GH_TOKEN_DAIDALA_PROJECT_MGMT` assignment from this profile file;
that attended credential remains in `gh-vault`. Restart the profile gateway so
the service reloads the runtime environment, then verify names only:

```bash
hermes -p daidala-self-improvement gateway restart
grep -q '^GH_TOKEN_DAIDALA_READ_ISSUES=' "$profile_env"
grep -q '^GH_TOKEN_DAIDALA_WRITE_ISSUES=' "$profile_env"
! grep -q '^GH_TOKEN_DAIDALA_PROJECT_MGMT=' "$profile_env"
```

These checks print no values. Never run `cat`, `env`, `set`, or `printenv` against
the profile environment as setup evidence.

### 3.4 Understand how password-manager entries connect to aliases

An "external credential manager" means a user-owned password manager such as
Bitwarden or KeePass, an operating-system secret store, or an organization
vault. It is not a GitHub Project feature and Daidala does not currently connect
to any of these products.

The names in trusted registration are logical identifiers only:

```yaml
credentials:
  intake: github-daidala-read-issues
  findings: github-daidala-write-issues
```

Creating entries with matching names in Bitwarden or KeePass does not bind them
to Daidala. There is no name-based lookup, browser extension integration, or
implemented `bw`, `bws`, `keepassxc-cli`, or KeePass database adapter. The
implemented V1 bridge is explicit:

```text
registration alias
    -> profile-local credential binding
    -> named process environment variable
    -> GH_TOKEN for the bounded GitHub CLI subprocess
```

The profile-local binding will contain only the alias, resolver type
`environment`, and environment-variable name. It will never contain the token
value. Daidala will not auto-detect a password manager or invoke its CLI. The
operator may copy a token into the controller's protected environment or use a
user-owned launcher that retrieves it from Bitwarden/KeePass and injects it when
the controller starts. Product-specific launch commands remain undocumented
until exercised and verified.

This separation avoids coupling Daidala to a personal vault and keeps vault
unlocking, session lifetime, and master-password handling outside the agent and
GitHub adapters. The adapter receives only the resolved runtime credential,
passes it as `GH_TOKEN` to the required `gh` subprocess, and must never print,
persist, hash, or return it as evidence.

Store the non-secret bindings beside the trusted registration as
`credential-bindings.yaml`:

```yaml
schema: daidala.credential-bindings/v1
project_id: forgegod-daidala
bindings:
  - alias: github-daidala-read-issues
    resolver: environment
    environment_variable: GH_TOKEN_DAIDALA_READ_ISSUES
  - alias: github-daidala-write-issues
    resolver: environment
    environment_variable: GH_TOKEN_DAIDALA_WRITE_ISSUES
```

The two explicit variables must be distinct and must not be named `GH_TOKEN`.
The checker resolves one only at its bounded GitHub call, constructs a minimal
child environment, and maps that value to `GH_TOKEN`. Missing variables,
unsupported resolvers, duplicate aliases, reused variables, unknown fields, and
embedded credential values fail before a GitHub command runs.

### 3.5 Record aliases without recording secrets

Retain a redacted setup record containing only:

- alias name;
- token type (`classic` or `fine-grained`);
- resource owner and selected repository where applicable;
- granted permission names;
- expiration date; and
- successful read-probe timestamp.

Never record the token value, prefix, suffix, fingerprint derived from the
token, or credential-manager export. Do not add either token to GitHub Project
fields, repository variables, repository secrets, `registration.yaml`, command
arguments, committed files, or evaluation results.

Do not grant `repo`, `public_repo`, `Contents`, `Administration`, pull-request,
workflow, deployment, release, or package write permissions. Public repository
content remains publicly readable; the boundary denies authenticated content
mutation rather than pretending public data can be hidden.

The operator command above updates the interactive `gh` credential only. It
does not create either runtime alias.

Retain non-secret capability metadata and prior approved receipts in sibling
`prerequisite-evidence.json`. Its strict
`daidala.prerequisite-evidence/v1` object binds the project ID, approved
controller revision, unchanged sticky profile, exact allowed and denied
credential capabilities, GitHub Project identity and required fields,
notification alias and receipt, and evaluator isolation receipt. It contains no
token, token-derived value, private destination ID, or raw command output.

```json
{
  "schema": "daidala.prerequisite-evidence/v1",
  "project_id": "forgegod-daidala",
  "approved_controller_revision": "afe1805fca5e27edc2e70ac526a697e76d8890fb",
  "sticky_profile": "hermes-vc",
  "credential_capabilities": [
    {
      "alias": "github-daidala-read-issues",
      "capability": "github-intake",
      "allowed": ["read-project", "read-public-repository"],
      "denied": ["contents-write", "administration", "merge", "release", "deployment"],
      "expires_on": "<YYYY-MM-DD>",
      "read_probe_receipt": "<approved-receipt-id>",
      "write_probe_identity": null
    },
    {
      "alias": "github-daidala-write-issues",
      "capability": "github-findings",
      "allowed": ["metadata-read", "issues-read-write"],
      "denied": ["contents-write", "administration", "merge", "release", "deployment"],
      "expires_on": "<YYYY-MM-DD>",
      "read_probe_receipt": "<approved-receipt-id>",
      "write_probe_identity": "<approved-controlled-issue-id>"
    }
  ],
  "github_project": {
    "owner": "forgegod",
    "project_id": "PVT_kwHOAAjENs4Bd2Xo",
    "url": "https://github.com/users/forgegod/projects/1",
    "fields": [
      "category", "priority", "readiness", "claim-owner",
      "claim-lease-expiry", "cycle-id", "workflow-id",
      "terminal-comparison-outcome"
    ],
    "read_probe_receipt": "<approved-receipt-id>"
  },
  "notification": {
    "adapter": "hermes-gateway",
    "target_alias": "attended-daidala",
    "authorized_maintainer": "forgegod",
    "receipt_id": "<approved-receipt-id>"
  },
  "evaluator": {
    "backend": "restricted-container",
    "network": "denied-by-default",
    "image_identity": "<pinned-image-identity>",
    "fresh_home": true,
    "network_denied": true,
    "controller_credentials_absent": true,
    "bounded_mounts": true,
    "receipt_id": "<approved-receipt-id>"
  }
}
```

Use `null` for a Project, notification, or evaluator record that has not been
produced by its separately approved setup probe; the matching check remains
`blocked`. Do not invent receipt IDs to make diagnosis pass.

If the available credential cannot be represented with these boundaries, stop
and provision a narrower GitHub App or fine-grained token. A broad operator
token is not silently accepted as either runtime alias.

## 4. Create the controller profile without changing the default

This command intentionally clones controller model credentials and skills from
`hermes-vc`. It does not clone sessions or memory. Do not use this operation for
an evaluator.

```bash
hermes profile create daidala-self-improvement \
  --clone-from hermes-vc \
  --description 'Coordinates one approval-gated Daidala self-improvement cycle.'
hermes -p daidala-self-improvement config set terminal.cwd \
  /home/raphael/src/rb/daidala
```

Do not run `hermes profile use`; the sticky default must remain unchanged.
Verify:

```bash
hermes profile show daidala-self-improvement
hermes profile list
```

The controller model remains explicit in the profile. Changing it is a separate
configuration decision and changes comparison inputs.

## 5. Verify the Daidala plugin in the controller

`plugins enable` does not install or discover a checkout. Daidala does not need
to be published to PyPI: Hermes v0.18.2 supports Git repository installation and
directory plugins. The persistent controller must load one exact committed
last-known-good revision, never the mutable working checkout.

The approved controller revision is
`afe1805fca5e27edc2e70ac526a697e76d8890fb`. It is:

- synchronized across local `HEAD`, `origin/main`, and remote `main`;
- contains the required evaluator and comparison implementation; and
- verified by the repository gate and detached-clone check.

Revision approval does not authorize installation. The controller profile has
no Daidala plugin. After separate setup approval, choose exactly one detached
installation path. Both supported paths pass isolated Hermes v0.18.2 discovery
and pack validation.

### 5.1 Install an approved revision from GitHub

Use this path while the selected commit remains reachable from the public remote.
PyPI publication is not required. `hermes plugins install forgegod/daidala`
tracks the repository branch and cannot pin a commit, so it is not accepted for
the persistent controller.

```bash
(
set -euo pipefail
approved_revision=afe1805fca5e27edc2e70ac526a697e76d8890fb
remote=https://github.com/forgegod/daidala.git
profile_home="$(dirname "$(hermes -p daidala-self-improvement config path)")"
plugin_dir="$profile_home/plugins/daidala"

test ! -e "$plugin_dir" && test ! -L "$plugin_dir"

mkdir -p "$profile_home/plugins"
git clone --no-checkout "$remote" "$plugin_dir"
git -C "$plugin_dir" cat-file -e "$approved_revision^{commit}"
git -C "$plugin_dir" checkout --detach "$approved_revision"
hermes -p daidala-self-improvement plugins enable daidala
)
```

### 5.2 Install an approved but unpushed local commit

Use a detached clone when the approved commit exists locally but is intentionally
not pushed. Do not symlink the mutable checkout and do not install its editable
virtualenv into Hermes.

```bash
(
set -euo pipefail
profile_home="$(dirname "$(hermes -p daidala-self-improvement config path)")"
plugin_dir="$profile_home/plugins/daidala"
approved_revision=afe1805fca5e27edc2e70ac526a697e76d8890fb
test ! -e "$plugin_dir" && test ! -L "$plugin_dir"

git -C /home/raphael/src/rb/daidala cat-file -e \
  "$approved_revision^{commit}"

mkdir -p "$profile_home/plugins"
git clone --no-hardlinks --no-checkout \
  /home/raphael/src/rb/daidala "$plugin_dir"
git -C "$plugin_dir" checkout --detach "$approved_revision"
hermes -p daidala-self-improvement plugins enable daidala
)
```

If the target exists, stop and inspect it; never overwrite or update it
implicitly. If Hermes asks whether Daidala may replace built-in tools, answer
**No**. Daidala does not require `--allow-tool-override`.

### 5.3 Verify discovery and exact identity

```bash
profile_home="$(dirname "$(hermes -p daidala-self-improvement config path)")"
plugin_dir="$profile_home/plugins/daidala"
approved_revision=afe1805fca5e27edc2e70ac526a697e76d8890fb

test "$(git -C "$plugin_dir" rev-parse HEAD)" = "$approved_revision"
git -C "$plugin_dir" status --short
hermes -p daidala-self-improvement plugins list --plain --no-bundled
hermes -p daidala-self-improvement daidala packs validate addyosmani
hermes -p daidala-self-improvement daidala packs validate aidlc
```

The revision must equal the approved 40-character identity, status output must
be empty, the list must show enabled Daidala `0.2.0` without an import error, and
both pack validations must return success. Record the revision as setup evidence.
A candidate Daidala build must never replace this loaded controller installation;
candidates run only in fresh evaluators.

## 6. Create the dedicated board

Create the named board without `--switch`, so the operator's current board is
not changed:

```bash
hermes kanban boards create daidala-forgegod-daidala \
  --name 'Daidala self-improvement' \
  --description 'One active, approval-gated forgegod/daidala cycle.' \
  --default-workdir /home/raphael/src/rb/daidala
```

Verify exact identity and isolation:

```bash
hermes kanban boards list
hermes kanban --board daidala-forgegod-daidala stats
hermes kanban boards show
```

If the slug already exists with a different description, default workdir, or
project ownership, stop. Never reuse a board based on display name alone.

## 7. Configure an attended gateway target

Run the controller profile's interactive platform setup and configure one
attended destination owned by the operator:

```bash
hermes -p daidala-self-improvement gateway setup
hermes -p daidala-self-improvement gateway start
hermes -p daidala-self-improvement gateway status
```

From the chosen chat, use `/sethome`, then send a test message and retain the
returned platform/chat/thread identity as the profile-local destination behind
alias `attended-daidala`.

The alias is not sufficient evidence by itself. Setup passes only when:

- the gateway is running;
- the target is allowlisted or paired;
- the operator receives a probe carrying a verifiable receipt identity;
- approval waits, failures, recovery blocks, and completion can reach the same
  attended target; and
- no credential or private destination ID is committed to the repository.

This CLI session is not a gateway delivery target. Local output is acceptable
only for an observed manual run and does not authorize unattended cron.

Telegram is configured as the controller profile's home platform and the
systemd gateway is running. Do not record the
private chat identity in this repository. `SI-NOTIFICATION` remains blocked
until an approved test delivery returns a receipt ID and that receipt is stored
only in profile-local prerequisite evidence.

## 8. Create and verify the GitHub projection

Do this only after the least-privilege aliases and Project scopes pass and after
separate GitHub-mutation approval. Idempotently create the labels required by
[the Daidala instance plan](plans/2026-07-13-daidala-self-improvement-loop.md),
verify the committed issue form, and create or locate the dedicated Project.
Record returned IDs and URLs in profile-local setup evidence.

Required labels:

- `daidala-si`;
- `daidala-si:ready`
- `daidala-si:claimed`
- `daidala-si:blocked`
- `daidala-si:accepted`
- `daidala-si:rejected`
- `daidala-si:sync-pending`
- category labels `daidala-si:regression`, `daidala-si:improvement`,
  `daidala-si:compatibility`, `daidala-si:skill-gap`, and
  `daidala-si:research-candidate`; and
- priority labels `daidala-si:priority-1` through `daidala-si:priority-5`.

In GitHub, open **forgegod/daidala > Issues > Labels** and create each exact
name. Descriptions and colors are presentation only; names are identity. Do not
create aliases or differently-cased duplicates.

On a fresh installation, verify that no Project with the fixed title exists,
then create it once:

```bash
gh-vault run --name ghcli -- \
  gh project list --owner @me --limit 100 --format json
gh-vault run --name ghcli -- \
  gh project create --owner @me \
    --title 'Daidala self-improvement' --format json
```

Do not run the create command when the title already exists. The current
instance is private user-owned Project 1 with node ID
`PVT_kwHOAAjENs4Bd2Xo`. Open that Project and create these exact lowercase field
names:

| Field | Type | Options or format |
|---|---|---|
| `category` | Single select | `regression`, `improvement`, `compatibility`, `skill-gap`, `research-candidate` |
| `priority` | Single select | `1`, `2`, `3`, `4`, `5` |
| `readiness` | Single select | `not-ready`, `ready`, `claimed`, `blocked`, `accepted`, `rejected`, `sync-pending` |
| `claim-owner` | Text | Stable actor identity. |
| `claim-lease-expiry` | Date | UTC lease expiry. |
| `cycle-id` | Text | Deterministic Daidala cycle ID. |
| `workflow-id` | Text | Equal to the deterministic cycle ID. |
| `terminal-comparison-outcome` | Single select | `retained`, `reverted`, `rejected`, `blocked`, `incomparable`, `no-change` |

Under the Project's **Workflows**, configure **Auto-add to project** with filter
`repo:forgegod/daidala is:issue label:daidala-si`, then enable the workflow.
Auto-add is presentation only: an issue is still ineligible until a maintainer
adds `daidala-si:ready` and the structured issue body validates.

Verify read access without changing Project state:

```bash
gh-vault run --name ghcli -- \
  gh project list --owner @me --limit 100 --format json
gh-vault run --name ghcli -- \
  gh project field-list 1 --owner @me --limit 100 --format json
gh-vault run --name ghcli -- \
  gh label list --repo forgegod/daidala --limit 200 --json name
```

The setup must retain the returned Project node ID, URL, number, and exact field
inventory. Project number and Project node ID are different values; do not use
one in place of the other.

A label or Project with the expected display name but an unverified remote ID is
not accepted. Daidala does not yet implement the planned `projects` onboarding
command or concrete GitHub mutation adapter. Project creation is therefore an
attended `gh` action, while labels, fields, and auto-add remain separately
approved manual UI actions until their mutation commands are implemented and
exercised. The operator credential must never become a runtime alias.

## 9. Materialize trusted registration

After all capability probes pass, write the registration below the controller's
Hermes-resolved profile root:

```text
/home/raphael/.hermes/profiles/daidala-self-improvement/
  projects/forgegod-daidala/
    registration.yaml
    credential-bindings.yaml
    prerequisite-evidence.json
```

Use this exact non-secret shape and replace only the maintainer identity if the
verified gateway authorization identity differs:

```yaml
schema: daidala.controller-registration/v1
project_id: forgegod-daidala
checkout: /home/raphael/src/rb/daidala
controller_profile: daidala-self-improvement
board: daidala-forgegod-daidala
repository_identity:
  canonical: forgegod/daidala
  verified_remote: git@github.com:forgegod/daidala.git
credentials:
  intake: github-daidala-read-issues
  findings: github-daidala-write-issues
approval:
  maintainers:
    - forgegod
notifications:
  adapter: hermes-gateway
  target: attended-daidala
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

The repository manifest may narrow this registration but cannot grant any of
its local authority.

## 10. Run the prerequisite checker

Status: **IMPLEMENTED AND REPOSITORY-TESTED.** The command is diagnostic only.
The setup remains blocked until installation, registration, and retained
receipts are complete and the checkout is clean.

The shared `doctor` command is the only prerequisite checker:

```bash
# Repository-local checks; live checks remain not-run
daidala doctor \
  --project-manifest .daidala/project.yaml

# Complete non-mutating check in the controller profile
hermes -p daidala-self-improvement daidala doctor \
  --project-manifest /home/raphael/src/rb/daidala/.daidala/project.yaml \
  --registration /home/raphael/.hermes/profiles/daidala-self-improvement/projects/forgegod-daidala/registration.yaml \
  --live
```

The checker will:

- emit one `daidala.prerequisite-report/v1` JSON document;
- report every stable `SI-*` row below exactly once;
- link each result to this guide's remediation section;
- bound and redact evidence without reading or printing credentials or private
  destination identities;
- return `0` only when every required check passes, `2` when a check is blocked
  or not run, and `1` for invalid input or checker failure; and
- produce equivalent output and exit codes through standalone `daidala` and
  native `hermes daidala` entry points.

Without `--live`, checks requiring GitHub, gateway delivery, or container
execution remain `not-run`, so the aggregate result cannot pass. `--live` still
performs diagnosis only: no profile or board creation, credential storage,
notification send, GitHub mutation, evaluator launch, admission, `--fix`, or
`--apply` is allowed.

The checker validates retained capability metadata and receipts created by
separately approved setup or cycle actions. It does not create its own passing
evidence. A missing notification receipt, evaluator-isolation result, or
credential capability record is reported as `blocked` with the matching guide
section.

The implementation test must extract the stable IDs from this document and
require exact equality with the CLI registry. Adding, removing, or renaming a
row therefore requires one reviewed change to this guide, the checker, its
tests, and the applicable plans. Explanations and remediation remain here; CLI
output stays concise and points back to this guide.

## 11. Ready-to-admit gate

Every row must pass before creating the controlled UC-01 issue or workflow:

| Check ID | Check | Required evidence | Guide |
|---|---|---|---|
| `SI-PROFILE` | Profile | Exact profile path, model/provider identity, plugin identity, and unchanged sticky default. | Sections 4-5 |
| `SI-BOARD` | Board | Exact board slug, default workdir, empty/expected task inventory. | Section 6 |
| `SI-REPOSITORY` | Repository | Canonical owner/repo, exact SSH remote, clean baseline revision. | Sections 1 and 9 |
| `SI-PACKS` | Packs | Both source revisions and packaged content digests validate. | Section 5 |
| `SI-GITHUB-INTAKE` | GitHub intake | Read alias proves only required read capabilities. | Sections 3.2 and 3.4 |
| `SI-GITHUB-FINDINGS` | GitHub findings | Alias metadata grants issue-only mutation; the first separately approved controlled issue must later return the write-probe identity. | Sections 3.3 and 3.4 |
| `SI-GITHUB-PROJECT` | Project | Returned Project ID/URL and required fields. | Sections 3.1 and 8 |
| `SI-NOTIFICATION` | Notification | Attended probe receipt and authorized maintainer identity. | Section 7 |
| `SI-EVALUATOR` | Evaluator | Fresh container, denied network, no controller credentials, bounded mounts. | Section 2 |
| `SI-REGISTRATION` | Registration | Strict parse, manifest binding, and capability probes all pass. | Section 9 |
| `SI-ACTIVE-CYCLE` | Active cycle | No active Daidala admission, board owner, worktree, evaluator, or adapter claim. | Section 11 |

If one row fails, record the exact blocker in the versioned evaluation result and
stop. Do not downgrade the requirement or convert repository tests into live
evidence.
