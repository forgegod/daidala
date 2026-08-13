# CHG-0009: GitHub repository registration and delivery authority

**Status:** in-progress
**Source request:** Direct operator request: "According to the skills create the CHR and design as proposed including the CLI and dashboard support. Do not execute before approval. In order to secure the PAT make a recommendation how to store the PAT in a secure way"; clarification: "I mean CHG"
**Affected capabilities:** CAP-0003, CAP-0004, CAP-0005
**Created:** 2026-08-11
**Scope amendment:** The approved scope includes Hermes secret-source and secret profile-aliasing design, explicit controller-profile selection in CLI/dashboard concepts, and review-only Pencil wireframes. Phase entry found that a repository URL and committed manifest cannot supply the board, intake/findings aliases, maintainer identities, attended destination, evaluator policy, or limits required by the strict controller-registration record. The registration slice therefore adds one strict profile-local `repository-registration-defaults.yaml` prerequisite. Preview reads that record without exposing private values; apply still writes exactly the two approved project-local records and blocks when the prerequisite is missing or invalid.

## Outcome

An operator can preview and explicitly register one GitHub repository for one
controller profile, then—only after an accepted exact review—preview and confirm
one reviewed commit/push to the derived `daidala/<workflow-id>` branch. Delivery
uses a dedicated profile-local credential binding and records only path-free
branch/commit receipt evidence before it releases the owned worktree.

## Scope

- Design one deterministic `daidala project register` preview/apply workflow and one Config → Repositories dashboard workflow backed by the same Python service. The dashboard must not start a nested CLI process.
- Accept only pasteable GitHub.com repository page or clone URLs, normalize them to `owner/repository`, and reject credentials, local paths, non-GitHub hosts, query/fragment strings, and repository sub-resource URLs.
- Make preview read the repository metadata and committed `.daidala/project.yaml` through the host's existing read-only GitHub CLI authentication. Preview must fail closed for an inaccessible repository, malformed/missing manifest, canonical identity mismatch, allowed-remote mismatch, duplicate project ID, or stale confirmation digest.
- Keep checkout paths, controller data roots, environment-variable names, credential values, GitHub Project node IDs, and target worktree content outside browser requests and responses. The UI may show an explicit Hermes profile and safe secret-alias/readiness state, but never a secret value, vault item, bootstrap token, or source command. The one intentional browser input is the GitHub.com link; after inspection the UI presents its derived `owner/repository` identity rather than treating a pasted remote as configuration authority.
- Persist only strict non-secret registration and credential-binding records after an exact preview digest and explicit confirmation. A static registration may remain diagnostically blocked while its real credentials are not available; it must not fabricate prerequisite evidence.
- Read controller authority from a strict profile-local `repository-registration-defaults.yaml` prerequisite because those values are neither repository policy nor safe browser inputs. Registration never creates or edits that prerequisite and browser responses expose readiness booleans rather than its private destination or environment bindings.
- Implement a separate attended delivery-authority record and exact commit/push
  transaction. It requires accepted review, the exact current diff and changed
  paths, `release.allow_commit: true`, `release.allow_push: true`, fresh preview
  confirmation, a dedicated delivery credential, and only the derived
  `daidala/<workflow-id>` branch.
- Exclude default-branch pushes, pull-request creation, merge, release, publication, GitHub App support, direct password-manager invocation from Daidala, credential-manager auto-detection, and any token input in the dashboard.
- Do not modify runtime Python, CLI registration, dashboard routes/assets, project manifests, credentials, release flags, or current CAP records before human approval.

## Design

### CLI

The planned command is `daidala project register --github-url URL [--profile NAME]`. It uses the shared registration service and is preview-only unless an operator supplies the displayed preview digest plus an explicit apply confirmation. The active Hermes profile is the default; an explicit profile must be an existing Hermes profile and is bound into the preview digest. `--profile` selects profile-local Daidala state; it is not a custom secret-alias option.

```text
$ daidala project register --github-url https://github.com/acme/payments-service
preview: valid
repository: acme/payments-service
project ID: acme-payments-service
controller profile: daidala-self-improvement
manifest: 6f12…9c80
registration: would write two non-secret profile-local records
delivery secret alias: not configured — does not block registration
next: repeat with --apply --expected-preview-digest 6f12…9c80 --confirm register-repository
```

`--apply` repeats inspection and validation before the profile-local atomic write. It does not clone a target checkout, create a GitHub Project, commit, push, or accept a credential value. A private repository that the host GitHub CLI cannot read reports a sanitized blocked result and directs the operator to authenticate the host outside Daidala.

### Dashboard: Config → Repositories

The primary registration screen reuses the existing dark teal, cream, amber, and green Hermes dashboard language. It is a three-state wizard, not a repository editor. It identifies the selected Hermes profile and shows only safe secret-profile aliasing/readiness state. It never exposes a profile wrapper alias, raw secret name, source command, vault item, or token.

```text
CONFIG / REPOSITORIES                                             [Refresh]

REGISTER A GITHUB REPOSITORY
Paste a GitHub.com repository link. Daidala inspects the committed project
policy before writing profile-local configuration.

GitHub repository link
[ https://github.com/acme/payments-service                         ] [Inspect]

Supported: github.com/owner/repository or a GitHub clone URL

────────────────────────────────────────────────────────────────────────────

REPOSITORY IDENTITY                         CONTROLLER READINESS
acme/payments-service                       Profile: daidala-self-improvement
Project ID: acme-payments-service            ✓ Board selected
Manifest: 6f12…9c80                          ✓ Attended target configured
Release: commit off · push off               ! Delivery secret source not configured

This screen never accepts a path, token, credential alias, or environment value.

[Back]                                            [Register repository]
```

The confirmation state names the canonical repository and profile, says that exactly two non-secret profile-local records will be written, and explicitly states that registration will not commit, push, create a GitHub Project, or store a token. Invalid, inaccessible, manifest-mismatch, stale-preview, incomplete-prerequisite, and registered states are visible and have no bypass control.

### Dashboard: workflow delivery

Workflow detail now exposes a closed delivery preview/apply route. It presents
only the derived branch, baseline, review digest, reviewed changed paths,
credential availability, and fresh preview digest. The only destructive action
is `Confirm commit and push branch`; it requires a literal checkbox and is
unavailable for missing credential authority. The server rejects false release
flags, stale evidence, blocking review, changed registration/remote, and branch
conflicts. The panel never displays an authentication form, credential alias,
token, worktree path, or default-branch action.

### Capability and wireframe boundary

CAP-0003 remains the dashboard baseline. CAP-0004 (GitHub repository
registration) and CAP-0005 (reviewed GitHub delivery) now describe their
implemented, test-backed surfaces and link their generated HTML/PNG wireframes.
The review-only Pencil package in
[`design.md`](CHG-0009-github-repository-registration-and-delivery/design.md)
remains CHG-owned provenance rather than a product-wireframe source.

When implementation is approved, the first registration vertical slice must create CAP-0004 plus its generated HTML/PNG wireframe before runtime UI work. The later delivery slice must create CAP-0005 plus its generated HTML/PNG wireframe. As defined by the repository-owned [capability-wireframes skill](../../../skills/software-development/capability-wireframes/SKILL.md), `docs/product/wireframes/generate.mjs` is the editable source that generates the `html/CAP-NNNN-<slug>.html` screen, `manifest.json`, and `index.html`; it then renders the matching `exports/CAP-NNNN-<slug>.png`. Both CAP screen pairs will be added in the same slice as runtime source and executable tests.

The product generator owns all three implemented screen entries, generated HTML,
manifest/index inventory, and 1440 × 960 PNG exports. The CHG review package
remains provenance; it is not a product-wireframe source.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Wireframe generator preparation | done (`node docs/product/wireframes/generate.mjs --render`; CAP-0003 outputs byte-identical) | The generator supports multiple current CAP entries without creating planned entries. |
| Approval boundary | done (direct operator approval: "Approve CHG-0009") | Direct operator approval of this CHG scope, Hermes secret-source/profile-aliasing approach, review wireframes, and branch-only delivery rule. |
| Repository registration vertical slice | done (`.venv/bin/pytest -q tests/test_repository_registration.py tests/test_cli.py tests/test_dashboard_api.py tests/test_dashboard_assets.py`; `.venv/bin/ruff check .`; `.venv/bin/python scripts/check_records.py .`; `.venv/bin/python scripts/check_md_links.py .`; `.venv/bin/daidala packs validate addyosmani`; `.venv/bin/daidala packs validate aidlc`) | CLI/dashboard adapters, CAP-0004 wireframe, and focused end-to-end tests passed. |
| Delivery authority and branch publish vertical slice | done (`tests/test_delivery.py`, dashboard/API/assets, execution/tool/plugin/worker-contract suites; `python scripts/check_records.py .`; `python scripts/check_md_links.py .`; `lefthook validate`; `pytest`; `ruff check .`; both pack validations; `python -m build`; `twine check dist/*`; release-content check) | The implementation and complete repository gate passed. No external credential, target repository commit, or GitHub push was exercised. |
| Closeout | in-progress | Final diff/security review remediated real preview-shape alias redaction across the CLI/dashboard projection; human review remains required before marking the CHG done and moving it to archive. |

## Decisions

- Use one deterministic repository-registration service for CLI and dashboard adapters. This prevents CLI/dashboard policy drift and avoids a nested command bridge.
- Keep non-repository controller authority in one strict profile-local defaults record that registration reads but never mutates. This resolves values that cannot be derived safely while preserving the one-link browser input and exact two-record apply boundary.
- Treat a pasted link as an untrusted identity claim. Canonical identity and manifest policy are derived and revalidated by the service before a profile write.
- Keep registration and content delivery as different authorities. Registering a repository cannot grant commit or push authority.
- For delivery V1, prefer a dedicated GitHub fine-grained PAT restricted to one repository with `Contents: read and write` only. Do not reuse the intake or findings tokens, and do not grant administration, issues, pull-request, workflow, deployment, release, package, or broad `repo` authority.
- Keep one explicit Daidala logical alias bound to a canonical credential-shaped environment variable such as `DAIDALA_GITHUB_DELIVERY_TOKEN`. Hermes `secrets.profile_alias` supplies the canonical value from a profile-suffixed secret at startup. Daidala must never compute its own suffix or invent alias precedence.
- Adopt Hermes secret sources as the operator-facing boundary: Bitwarden Secrets Manager is the preferred shared/automated option; 1Password and a bounded non-interactive command helper remain valid alternatives. A profile with no source is valid but delivery-blocked. Daidala never invokes `bws`, `op`, KeePass, or a helper directly.
- For Bitwarden, a narrowly scoped machine account and project hold repository/environment-specific delivery PATs. Its bootstrap token stays in the Hermes-home `.env` with owner-only protection, never in the repository, Daidala records, browser, command line, or `config.yaml`. Source precedence, `override_existing`, and `secrets.preserve_existing` remain Hermes configuration decisions.
- The CLI and dashboard select one existing Hermes profile explicitly. The preview digest binds that profile and the non-secret proposed writes. The dashboard may show selected-profile and alias/readiness state, but never a raw secret name, source command, vault item, bootstrap token, or credential value.
- The delivery adapter receives the resolved value only in a minimal child environment for the bounded Git subprocess, disables terminal prompts, and never puts it in a URL, argument, Git config, receipt, browser response, artifact, or log. A missing value blocks delivery; it never triggers stale, cross-profile, or guessed fallback behavior.
- Persist a preview-bound authorization before the branch commit, then require its
  exact commit/remote-ref receipt before completing the Deliver card and
  releasing the worktree. A retry may resume only that exact transaction. If
  completion succeeded but worktree release was interrupted, recovery additionally
  requires the live Deliver card's sole completed run to carry that exact
  non-secret branch/commit receipt.
- Do not rely on Git Credential Manager for this design: at design time this host has no configured `credential.helper` and no `git-credential-manager` executable. Do not install or configure one as part of this CHG.
- Record only redacted capability metadata for the delivery credential: logical alias, source/readiness category, token class, owner/repository restriction, permission names, expiration date, and successful probe timestamp. Rotate before expiry and revoke immediately after suspected exposure or authorization failure.

## Evidence

- Direct operator approval: "Approve CHG-0009". This authorizes implementation of the approved registration, secret-source/profile-aliasing, review-wireframe, and branch-only delivery scope; it does not bypass phase gates or attended delivery confirmation.
- Review-only design package: [`design.md`](CHG-0009-github-repository-registration-and-delivery/design.md), its [Pencil source](CHG-0009-github-repository-registration-and-delivery/wireframes/repository-registration-and-delivery.pen), and native [registration](CHG-0009-github-repository-registration-and-delivery/wireframes/exports/repository-registration.png) and [delivery](CHG-0009-github-repository-registration-and-delivery/wireframes/exports/delivery-authority.png) PNGs. It is not a CAP-linked current-product wireframe and grants no runtime authority.
- Current contract evidence: [`docs/16-self-improvement-setup.md`](../../16-self-improvement-setup.md) documents explicit environment bindings; [`docs/01-architecture.md`](../../01-architecture.md), [`docs/02-workflow-state.md`](../../02-workflow-state.md), [`docs/06-security.md`](../../06-security.md), and [`docs/07-runbook.md`](../../07-runbook.md) own the implemented authority and operator boundary. Hermes secret-source behavior is governed by the [official Secrets guide](https://hermes-agent.nousresearch.com/docs/user-guide/secrets/).
- The review screens were compared with the locally running [Daidala Config view](http://127.0.0.1:9119/daidala?view=config) and preserve the complete Hermes shell and Daidala Config navigation from the historical review source. The local view is visual-reference evidence only; it confers no implementation authority.
- The registration core, CLI and dashboard adapters, CAP-0004, and its generated
  wireframe are implemented in the repository. No target repository registration,
  PAT, secret source, commit, push, or external GitHub action was exercised while
  implementing this change.
- Repository registration vertical-slice gate passed on 2026-08-13: record and
  Markdown-link checks, 156 focused registration/CLI/dashboard tests, Ruff, and
  Addyosmani and AI-DLC pack validation all completed successfully.
- State reconciliation: commits `8b37de7` and `c56e31e` contain the completed
  registration vertical slice and its recorded phase gate.
- Delivery-slice verification passed on 2026-08-13: record and Markdown-link
  checks (`5` capabilities, `11` CHGs, `3` wireframes; `98` documents),
  Lefthook, `pytest`, Ruff, both pack validations, package build,
  `twine check dist/*`, release-content (`289` tracked files, `66` wheel
  members), and `git diff --check`. The CAP-0005 PNG was visually inspected at
  its declared `1440 × 960` viewport with no clipping, overflow, or illegible
  controls. No real credential lookup, target commit, or push occurred.
- Post-review delivery recovery verification passed on 2026-08-13: a replay no
  longer repeats `kanban_complete`; it recovers a post-commit authorization
  persistence interruption and a post-completion worktree-release interruption.
  It fails closed when the live Deliver card lacks the exact
  `daidala.delivery/v1` branch/commit metadata in its single completed Hermes run.
  The full repository/release gate then passed again: record and Markdown-link
  checks, Lefthook, `pytest`, Ruff, both pack validations, package build,
  `twine check dist/*`, release-content (`289` tracked files, `66` wheel
  members), and `git diff --check`. No real credential lookup, target commit, or
  push occurred.
- Final delivery-surface review found that the internal preview serializer exposed
  the non-secret credential alias through CLI/dashboard output. The public
  projection now omits that alias while retaining it in the canonical
  preview/authorization identity; real-object CLI and dashboard API regression
  tests cover the boundary. The complete repository/release gate passed again
  after this remediation: records and Markdown links, Lefthook, full `pytest`,
  Ruff, both pack validations, package build, `twine check dist/*`,
  release-content, and `git diff --check`. Final human review is still pending.
