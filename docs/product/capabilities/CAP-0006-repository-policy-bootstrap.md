# CAP-0006: Repository policy bootstrap

**Status:** implemented
**Primary surface:** Daidala Config → GitHub Repositories (bootstrap path)

## Outcome

An operator can preview and explicitly publish conservative Daidala project
policy for a readable GitHub repository that lacks committed
`.daidala/project.yaml`, on a non-default branch, without registering the
repository or touching the default branch.

## Behavior

- `daidala project bootstrap --github-url URL --profile NAME` and Config →
  GitHub Repositories bootstrap use one deterministic bootstrap service.
- Bootstrap is offered only after inspect classification is `needs-bootstrap`.
- Preview generates strict `.daidala/project.yaml` and
  `.daidala/constraints.yaml` content with release flags false, pinned pack
  digests from the running Daidala install, and a derived project ID.
- Preview binds profile, canonical repository, base commit, target branch
  `chore/daidala-bootstrap-project-policy` (Conventional Commits–style
  `type/description` branch naming), and file digests. Apply requires the exact
  preview digest and literal confirmation `bootstrap-repository`.
- Apply creates blobs/tree/commit through host `gh` Git Data API calls and
  creates only that branch ref. It never updates the default branch, creates a
  pull request via API, merges, stores a token, or writes registration or
  credential-binding records.
- Preview and apply responses include public GitHub convenience links for the
  bootstrap branch, the `.daidala` tree on that branch, and GitHub’s
  compare/open-pull-request page (`expand=1`). Merge remains an operator action
  on GitHub outside Daidala.
- After the operator merges the bootstrap branch (typically via the linked
  compare/PR page), they use CAP-0004 registration against the default-branch
  manifest.

## Evidence

### Runtime

- [`daidala/repository_bootstrap.py`](../../../daidala/repository_bootstrap.py) — template generation, digest binding, host-`gh` branch publish.
- [`daidala/cli.py`](../../../daidala/cli.py) — `project bootstrap` preview/apply adapter.
- [`dashboard/plugin_api.py`](../../../dashboard/plugin_api.py) — path-free bootstrap preview/apply routes.
- [`dashboard/dist/index.js`](../../../dashboard/dist/index.js) — bootstrap confirmation UI on Config → GitHub Repositories.

### Tests

- [`tests/test_repository_bootstrap.py`](../../../tests/test_repository_bootstrap.py) — conservative template, branch-only apply, stale digest and existing-branch rejection.
- [`tests/test_repository_registration.py`](../../../tests/test_repository_registration.py) — `needs-bootstrap` classification.
- [`tests/test_dashboard_assets.py`](../../../tests/test_dashboard_assets.py) — bootstrap UI contract strings.

## Contracts

- [`docs/06-security.md`](../../06-security.md)
- [`docs/07-runbook.md`](../../07-runbook.md)
- [CAP-0004](CAP-0004-github-repository-registration.md)

## Links

- [CHG-0010](../../changes/archive/CHG-0010-non-daidala-repository-bootstrap.md)
- [CHG-0011](../../changes/archive/CHG-0011-bootstrap-branch-links.md)
- [CHG-0015](../../changes/archive/CHG-0015-all-profile-repository-inventory.md)
- [CHG-0017](../../changes/active/CHG-0017-start-repository-wording-and-inventory.md)
- [HTML wireframe](../wireframes/html/CAP-0006-repository-policy-bootstrap.html)
- [PNG wireframe](../wireframes/exports/CAP-0006-repository-policy-bootstrap.png)
