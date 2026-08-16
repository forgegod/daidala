# CHG-0022: Flip inspect to Apply default policy

**Status:** in-progress
**Source request:** Direct operator request: "if in the "GitHub Repositories" a repository is inspected where the default ".daidala" subdirectory is not applied, flip the "Inspecte repository" into "Apply default policy (checkin on main)" and proceed like with a new created working directory in a "new workflow". I thing we are doing a feature branch and an PR for approval the needed change"
**Affected capabilities:** CAP-0004, CAP-0006
**Created:** 2026-08-16

## Outcome

After inspect classifies a GitHub repository as `needs-bootstrap`, the same
row control becomes Apply default policy. Confirmed apply still publishes
conservative `.daidala` policy on the existing non-default bootstrap branch
and leaves pull-request creation to GitHub’s compare page.

## Scope

- Flip the Config → GitHub Repositories inspect control after
  `needs-bootstrap`; keep digest-bound confirmation.
- Reuse `RepositoryBootstrapService` unchanged: no default-branch write, no
  pull-request API, no registration or checkout.
- Update CAP-0004/CAP-0006, the CAP-0006 wireframe, dashboard contract tests,
  and the operator runbook sentence for the flipped control.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `.venv/bin/python -m pytest tests/test_dashboard_assets.py tests/test_repository_bootstrap.py tests/test_repository_registration.py tests/test_dashboard_api.py -q` |
| Closeout | in-progress | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check .` |

## Decisions

- Approved apply behavior is the current branch-only bootstrap engine with
  confirm plus preview digest. Daidala still does not check in on `main` or
  create a pull request via API.
- The flipped row button is the sole apply authority. The preview panel keeps
  the confirmation checkbox and consequence text.
- Apply writes a profile-local public compare/PR receipt. Inventory shows that
  link after a Hermes restart until the repository is registered.

## Evidence

- Focused dashboard/bootstrap/registration suite passed: 122 tests.
- `python scripts/check_records.py .` and `python scripts/check_md_links.py .` passed.
