# CAP-0004: GitHub repository registration

**Status:** implemented
**Primary surface:** Daidala Config → GitHub Repositories

## Outcome

An operator can preview and explicitly register one GitHub repository for one
existing Hermes controller profile without providing a filesystem path or
token to Daidala. Profile-local registration defaults are created, validated,
and saved through the CLI or Config wizard.

## Behavior

- `daidala project register --github-url URL --profile NAME --board SLUG` and
  Config → GitHub Repositories use the same deterministic registration service.
- Preview inspects the canonical GitHub identity and committed project policy,
  reports the derived project ID, release flags, safe readiness state, two
  proposed non-secret writes, and a digest bound to the profile and proposal.
- Inspect classifies a repository before registration: missing committed
  `.daidala/project.yaml` returns a path-free `needs-bootstrap` result with
  `next_action: bootstrap` and flips that row’s Inspect repository control to
  Apply default policy (CAP-0006); an already-registered project ID returns
  `already-registered`; other blocked causes return `blocked` with a stable
  reason. Only `registerable` yields a registration preview.
- Apply re-inspects the repository and accepts only the exact preview digest
  plus the literal `register-repository` confirmation. It binds an existing
  unused board with the derived checkout workdir or creates one with that
  workdir, then writes only controller registration and credential-bindings
  records.
- Config → GitHub Repositories lists every Hermes-validated profile and its
  workspace tuples in one inventory. A registered row shows canonical
  repository, project-id slug, board with path-free state (`bound`, `missing`,
  `workdir-mismatch`, or `in-use`), and GitHub Project link state. It fills the
  GitHub repository link field with `github.com/<repository_canonical>` and
  never exposes a profile root, checkout, credential alias, environment-variable
  name, or secret metadata.
- The dashboard accepts a GitHub URL, existing Hermes profile name, and an
  optional board slug for preview from the inventory row that owned the inspect
  action. Apply additionally accepts the digest and `confirm: true`; the server
  resolves the named profile through Hermes on every request and binds the
  preview digest to that profile.
- GitHub Contents API Base64 line wrapping is normalized before strict decoding;
  malformed non-Base64 content remains rejected.
- Public preview readiness exposes only `credential_available`; credential
  aliases and secret-source details remain internal to the profile-local
  registration and binding records.
- Registration requires profile-local
  `repository-registration-defaults.yaml`. Operators preview, seed, validate,
  and write that file with `daidala project defaults`; the example and field
  rules live in
  [Configure registration defaults](../../07-runbook.md#configure-registration-defaults).
  Config → GitHub Repositories shows a per-profile defaults wizard that
  previews, seeds, validates, and saves the same file. Registration never accepts or stores a token, creates a GitHub Project,
  creates a checkout, commits, pushes, publishes, or grants delivery authority.

## Evidence

### Runtime

- [`daidala/repository_registration.py`](../../../daidala/repository_registration.py) — canonical GitHub URL validation, preview digest, prerequisite validation, and atomic two-record write.
- [`daidala/cli.py`](../../../daidala/cli.py) — standalone and native CLI preview/apply adapter.
- [`dashboard/plugin_api.py`](../../../dashboard/plugin_api.py) — exact path-free dashboard request boundary.
- [`dashboard/dist/index.js`](../../../dashboard/dist/index.js) — Config → GitHub Repositories preview and explicit confirmation UI.

### Tests

- [`tests/test_repository_registration.py`](../../../tests/test_repository_registration.py) — deterministic registration core, defaults preview/apply, and fail-closed policy tests.
- [`tests/test_cli.py`](../../../tests/test_cli.py) — native/standalone registration and defaults preview/apply parity.
- [`tests/test_dashboard_api.py`](../../../tests/test_dashboard_api.py) — exact dashboard payload and confirmation boundary.
- [`tests/test_dashboard_assets.py`](../../../tests/test_dashboard_assets.py) — path-free browser surface contract.

## Contracts

- [`docs/06-security.md`](../../06-security.md) — Hermes-owned secret and generated-state boundary.
- [`docs/07-runbook.md`](../../07-runbook.md) — operator preview/apply procedure.
- [`docs/16-self-improvement-setup.md`](../../16-self-improvement-setup.md) — profile-local controller prerequisite guidance.

## Links

- [CHG-0009](../../changes/archive/CHG-0009-github-repository-registration-and-delivery.md)
- [CHG-0010](../../changes/archive/CHG-0010-non-daidala-repository-bootstrap.md)
- [CHG-0015](../../changes/archive/CHG-0015-all-profile-repository-inventory.md)
- [CHG-0017](../../changes/archive/CHG-0017-start-repository-wording-and-inventory.md)
- [CHG-0022](../../changes/active/CHG-0022-apply-default-policy-inspect-control.md)
- [CHG-0023](../../changes/archive/CHG-0023-registration-defaults-wizard.md)
- [HTML wireframe](../wireframes/html/CAP-0004-github-repository-registration.html)
- [PNG wireframe](../wireframes/exports/CAP-0004-github-repository-registration.png)