# GitHub repository registration and delivery — proposed design

**Status:** proposed — review-only; no runtime implementation is authorized
**Governing change:** [CHG-0009](../CHG-0009-github-repository-registration-and-delivery.md)
**Design artifacts:** [`repository-registration-and-delivery.pen`](wireframes/repository-registration-and-delivery.pen), [registration PNG](wireframes/exports/repository-registration.png), and [delivery PNG](wireframes/exports/delivery-authority.png)
**External basis:** [Hermes Secrets](https://hermes-agent.nousresearch.com/docs/user-guide/secrets/)

## Decision summary

| Concern | Proposed decision | Why |
|---|---|---|
| Registration authority | One deterministic Python service backs both CLI and dashboard adapters. | URL parsing, manifest validation, profile selection, preview digest, and atomic write rules cannot drift. |
| URL input | Accept only GitHub.com repository page/clone forms; normalize to `owner/repository`; reject all other URL/path forms. | A pasted URL is an untrusted identity claim, not registration authority. |
| Profile | Registration is written under one explicit, existing Hermes profile. CLI defaults to the active profile; the dashboard defaults to its current profile. | Registrations and credential bindings are profile-local. Cross-profile state needs explicit attended intent. |
| Hermes profile aliases | Use Hermes `secrets.profile_alias` only for profile-specific secret hydration. Do not invent a Daidala alias registry. | Hermes already owns source precedence and profile-suffixed credential resolution. |
| Credential aliases | Keep Daidala's explicit logical alias → canonical environment-variable binding. | Daidala needs deterministic, non-secret capability metadata; Hermes owns resolution. |
| Secret source | Daidala never calls a vault. Hermes hydrates secret sources at process startup; zero configured sources is a valid but delivery-blocked state. | Keeps credentials outside Daidala code, records, dashboard, and artifacts. |
| PAT | One dedicated fine-grained PAT per repository/environment, stored in Hermes's secret source, with `Contents: read and write` only. | Limits blast radius and separates delivery authority from intake/findings authority. |
| Delivery | Commit/push is a separate future capability with preview, digest, review, release-flag, branch, and human confirmation gates. | Registration must never confer write authority. |

## Current state and boundary

Daidala currently has profile-local manual registration records, strict credential alias bindings, and a dashboard that exposes configuration guidance. It does not expose `project register`, does not accept GitHub repository URLs, and does not commit or push a target repository. The project manifest intentionally retains `release.allow_commit: false` and `release.allow_push: false`.

This document designs future behavior only. It neither authorizes nor changes a Hermes secret source, `HERMES_HOME`, Daidala registration, token, CLI command, dashboard route, manifest, branch, GitHub repository, commit, or push.

## Approved wireframe-structure preparation

The approved preparation is limited to the existing product-wireframe generator: it now holds a plural current-CAP inventory and renders every listed entry. Regeneration preserves CAP-0003's HTML, manifest, index, and PNG byte-for-byte. This is preparation for the later registration and delivery slices, not a migration of proposed content into the current-product inventory.

The review-only Pencil source and PNGs remain under this CHG. CAP-0004 and CAP-0005 remain unallocated, and no planned HTML/PNG screen is listed under `docs/product/wireframes/`. When the registration slice is separately approved, it creates CAP-0004, adds its final screen definition to the generator, regenerates the product outputs, and links them with runtime behavior tests. The later delivery slice follows the same sequence for CAP-0005.

## Terminology

| Term | Meaning | Owner |
|---|---|---|
| Hermes profile | A named Hermes runtime/data isolation boundary such as `hermes-vc` or `daidala-self-improvement`. | Hermes |
| Profile wrapper alias | A `hermes profile alias` shell-wrapper name. | Hermes |
| Secret profile aliasing | Hermes startup behavior that hydrates a canonical credential-shaped environment variable from a matching profile-suffixed secret when enabled. | Hermes |
| Daidala credential alias | A non-secret slug in `credential-bindings.yaml`, mapped explicitly to one canonical environment variable. | Daidala |
| Secret source | Bitwarden, 1Password, or a configured command helper that Hermes runs during startup. | Hermes |
| Delivery credential | The future dedicated PAT for one repository's bounded commit/push adapter. | Operator and Hermes secret source |

The first two rows are deliberately distinct. This design uses **secret profile aliasing**, not `hermes profile alias` wrapper scripts. A profile wrapper alias must not alter credential selection, and a secret-profile alias must not redirect profile-local Daidala state.

## Registration concept

### Inputs and normalization

The shared service accepts a single `github_url` value. It permits GitHub.com repository page and clone forms only, removes a terminal `.git`, canonicalizes the result to `owner/repository`, and requires exactly two non-empty identifier segments. It rejects:

- user-info or credentials in a URL;
- non-HTTPS/non-SSH syntaxes that cannot be recognized as GitHub clone URLs;
- non-GitHub hosts, IP literals, ports, query strings, fragments, and sub-resource paths;
- local paths, `file:` URLs, scp-like arbitrary hosts, and shell-expanded input;
- malformed owner/repository names or inputs outside the bounded input size.

The service obtains the committed `.daidala/project.yaml` through the existing read-only GitHub authority, parses it strictly, and validates canonical identity and allowed remote policy before constructing a preview. It never accepts browser input as a checkout path, `verified_remote`, credential name, board, notification target, maintainer identity, or release policy.

### Profile selection

A registration preview has one explicit `controller_profile`:

1. The CLI defaults to the active Hermes profile when no `--profile` is supplied.
2. A supplied `--profile NAME` must name an existing Hermes profile; it is not a file path, a `HERMES_HOME` value, a wrapper alias, or an arbitrary data root.
3. The dashboard starts with the profile that owns its backend context. A profile picker may show only backend-validated existing profiles. Selecting another profile requires an explicit confirmation in the same preview/apply exchange.
4. The preview digest binds profile name, canonical repository identity, manifest digest, and every proposed non-secret profile-local write. Apply must reject a changed profile or a stale digest.

The selected profile determines where the registration and binding records are written and which Hermes process can later resolve the delivery credential. It does not copy registrations, secrets, or workflow state between profiles.

### Preview and apply

The default command is non-mutating:

```text
$ daidala project register --github-url https://github.com/acme/payments-service \
    --profile daidala-self-improvement

preview: valid
repository: acme/payments-service
project ID: acme-payments-service
controller profile: daidala-self-improvement
manifest digest: 6f12…9c80
registration: would write non-secret profile-local records
secrets: delivery credential is not configured; registration remains permitted
next: add --apply --expected-preview-digest 6f12…9c80 --confirm register-repository
```

`--apply` must re-fetch and revalidate before atomically persisting the displayed records. It requires `--expected-preview-digest` and a literal `--confirm register-repository`; it must not use a generic yes/no flag. It does not clone a target checkout, create GitHub Projects, configure Hermes secrets, write credentials, change a manifest, commit, push, or create a pull request.

No future CLI option may accept a PAT value, secret reference value, vault password, bootstrap token, or profile filesystem path. In particular, there is no `--token`, `--pat`, `--secret`, `--secret-profile-alias`, or `--hermes-home` option.

## Hermes secrets and profile aliasing

### Proposed environment contract

The future profile-local credential binding uses a canonical credential-shaped name such as:

```yaml
schema: daidala.credential-bindings/v1
project_id: acme-payments-service
bindings:
  - alias: github-repository-delivery
    resolver: environment
    environment_variable: DAIDALA_GITHUB_DELIVERY_TOKEN
```

The file contains no value. The canonical `*_TOKEN` shape deliberately participates in Hermes secret profile aliasing. When Hermes starts a named profile with `secrets.profile_alias` enabled (the documented default), a secret source can supply that profile's suffix form and Hermes hydrates the canonical variable the Daidala adapter reads.

The suffix spelling and normalization for profiles containing punctuation is Hermes-owned. The implementation must obtain the resolved profile-alias identity from Hermes, not reconstruct an environment-variable suffix in Daidala or display a guessed spelling in the dashboard. The UX may show `Profile-specific secret aliasing: active` and the selected profile; it must not show secret values.

A secret source that supplies the canonical environment variable directly wins over a profile alias. Therefore a shared vault must not define a canonical delivery-token entry when different profiles need distinct delivery authority. Define only the intended profile-specific secret entries and use Hermes source precedence deliberately.

### Source choices

| Source | Suitable use | Notes |
|---|---|---|
| Bitwarden Secrets Manager | Recommended for a shared controller or more than one Hermes installation. | Hermes has a native source. A narrowly scoped machine account fetches a project at startup. |
| 1Password | Valid alternative where an existing 1Password service-account or desktop-session model is already approved. | Hermes resolves `op://` references. |
| Command helper | KeePassXC, `secret-tool`, `pass`, or another existing local vault. | The helper is Hermes configuration, runs once at startup, is non-interactive, has a tight timeout, and emits only `KEY=VALUE` lines. |
| No source | Current accepted design state. | Registration can proceed; delivery remains visibly blocked and cannot fall back to a raw PAT. |

Daidala does not select, configure, invoke, or inspect a source. The dashboard must link to the Hermes Secrets guide and report only safe readiness facts: source configured/not configured, canonical binding present/absent, and credential available/unavailable. It must not render a source command, vault item, environment value, manager access token, or environment-variable name.

### Bitwarden recommendation

For a machine that will perform attended or automated delivery from more than one profile, Bitwarden Secrets Manager is the preferred path because Hermes hydrates it at startup and preserves source provenance. Create a dedicated Bitwarden project for Daidala delivery secrets and a machine account with read access to that project only. Store one restricted PAT per repository/environment under the profile-specific secret name Hermes expects.

The Bitwarden machine-account bootstrap token is a high-value credential. Hermes stores that one bootstrap token in the Hermes home `.env`, never in `config.yaml`, the repository, a Daidala record, a shell command, or the dashboard. It must reside on the Linux filesystem rather than a Windows-mounted workspace and have owner-only permissions. The setup is an explicit future operator action through the Hermes secret setup flow, not a Daidala operation.

Use `secrets.preserve_existing` only where an intentionally profile-local shell or `.env` value must beat a centrally managed source. Do not use it to keep an unrotated delivery PAT alive accidentally. A Bitwarden source normally overrides existing values; this is useful for rotation, but should be reviewed per variable before enablement.

### KeePass command-helper alternative

KeePass remains suitable when a local vault is the required store. Hermes's command source is the boundary: configure a short, non-interactive helper that unlocks nothing and prints a bounded dotenv map after the vault is already available to the host. The helper command is trusted configuration and its standard error is intentionally discarded by Hermes; it must be small, explicit, and independently reviewed.

Do not add KeePass CLI orchestration to Daidala. A long unlock/prompt/script sequence is a reason to write a dedicated Hermes secret-source plugin later, not to embed vault behavior in dashboard JavaScript or a Daidala adapter.

### Precedence and failure behavior

Hermes loads `.env`/shell values first, then secret sources. Mapped sources outrank bulk sources, and first source wins within the same shape. Source configuration can elect to override existing values; one source cannot replace another source's bootstrap token. The design relies on Hermes for these rules and adds no Daidala precedence.

Hermes startup does not fail merely because a source is unavailable. The future Daidala delivery preflight must therefore explicitly resolve the named logical credential and fail closed with `delivery credential unavailable`. It must not reuse a stale value, substitute a different profile's credential, or infer a vault item from a logical alias.

## Dashboard interaction design

The review-only Pencil screens show the proposed user interface.

### Config → Repositories

The registration screen has four persistent facts at the top:

- selected Hermes profile;
- profile-local registration destination, described without a filesystem path;
- host secret-alias state (`active`, `disabled`, or `not configured`); and
- safe delivery credential readiness (`unavailable` is non-blocking for registration).

The primary interaction is a GitHub.com URL field and `Inspect repository`. A successful inspection shows derived canonical identity, project ID, manifest digest, release policy, prerequisite checks, and the exact non-secret records that `Register repository` would write. The register control opens a confirmation state that binds the selected profile and current preview digest.

A profile picker does not expose wrapper aliases or secret names. It labels each selectable profile by its actual Hermes profile name and an availability state; it rejects missing/untrusted profiles and requires a fresh inspection after a profile change.

The review screen keeps two operator-instruction cards visible beside the registration preview. **Required GitHub access rights** says that a future branch-delivery credential must be a fine-grained PAT restricted to the selected repository with `Contents: read and write` only; it must not grant organization, Administration, Projects, Workflows, or default-branch authority, and it needs expiration, rotation, and revocation. **Store a token for the selected profile** says that the operator configures a Hermes-supported secret source outside Daidala, binds it to the displayed Hermes profile, and follows the [official Hermes Secrets guide](https://hermes-agent.nousresearch.com/docs/user-guide/secrets/). It explicitly states that neither the dashboard nor the CLI accepts or displays the value, that Daidala retains only a logical reference, and that Hermes resolves the value only for a bounded delivery operation.

### Delivery panel

The panel is a future disabled surface until its CAP and runtime service exist. It shows the selected controller profile and safe secret state, then requires accepted review, a fresh diff identity, release flags, an allowed Daidala branch, and an exact delivery preview. The future confirmation text says exactly what branch will be committed and pushed. It has no token field, no source configuration action, no default-branch option, no pull-request action, and no bypass for missing secret authority.

The disabled credential gate repeats the least-rights and selected-profile storage instructions with the official Hermes Secrets URL, so an unavailable delivery state gives an operator a safe next step without exposing a credential or turning registration into credential setup.

## Delivery transaction concept

A future delivery request contains only non-secret identifiers: project, selected profile, reviewed workflow/cycle, target Daidala branch, release-policy snapshot, and preview digest. The adapter resolves `github-repository-delivery` only immediately before its bounded Git action. The value must never be included in a subprocess argument, remote URL, Git config, browser response, exception, receipt, trace, telemetry field, or artifact.

The executable transaction is deliberately deferred. It must be implemented only after registration has a tested vertical slice and after separate approval of the following checks:

1. exact accepted review disposition and evidence;
2. clean, currently reviewed worktree and changed-path identity;
3. committed manifest permits commit and push;
4. protected target branch matches `daidala/<cycle-id>`;
5. selected profile equals the preview-bound profile;
6. logical alias has a single explicit canonical binding;
7. Hermes has supplied a non-empty credential to that canonical variable;
8. a fresh delivery digest and attended literal confirmation match.

## Threat controls

| Threat | Required control |
|---|---|
| Token in source, records, UI, or command history | No secret-bearing CLI arguments; no dashboard input; release-content scan; records hold aliases and safe metadata only. |
| Wrong profile receives a shared secret | Explicit profile binding; Hermes profile aliasing; preview digest binds profile; no Daidala custom alias mapping. |
| Central source silently overrides an intentional local credential | Document and review `override_existing` and `secrets.preserve_existing`; surface provenance/readiness, not values. |
| Missing source allows accidental delivery with stale data | Delivery resolves at operation time and blocks on unavailable credential. |
| A broad PAT compromises unrelated repositories | One fine-grained PAT per repository/environment, `Contents: read and write` only, short expiration, rotation, and revocation. |
| Registration becomes implicit write authority | Separate records, capabilities, UI states, approvals, and release flags. |
| A malicious URL changes checkout or remote identity | Strict parse; fetched manifest and allowed remote validate canonical identity; no browser-supplied paths. |
| Cross-profile filesystem access | Existing-profile validation and Hermes-resolved profile roots only; no arbitrary root/path option. |

## Documentation and implementation sequence

1. Review this document, its Pencil screens, and CHG-0009. Approve or amend the secret-source decision and selected-profile behavior.
2. Before runtime work, enable and independently verify a Hermes secret source only if delivery will be implemented. The source is not a registration prerequisite.
3. Implement one registration-only vertical slice: service, URL parser, profile validation, CLI preview/apply, dashboard route, tests, CAP-0004, and its current-state product wireframe.
4. Re-review delivery scope after registration evidence exists. Add CAP-0005, a current-state wireframe, delivery authority, bounded Git adapter, secrets/readiness tests, and exact approval gates only with a separate approval.

## Out of scope

- configuring a Hermes secret source, Bitwarden machine account, 1Password account, or KeePass helper;
- changing a profile wrapper alias or disabling/enabling Hermes secret profile aliasing;
- reading or creating any PAT, bootstrap token, vault entry, `.env` file, or credential binding;
- target repository checkout creation, commit, push, pull request, merge, release, publish, or GitHub App installation;
- runtime CLI/parser, dashboard route, browser asset, schema, test, CAP, or current-state product-wireframe implementation.
