# CHG-0022: Flip inspect to Apply default policy

**Status:** in-progress
**Source request:** Direct operator request: "if in the "GitHub Repositories" a repository is inspected where the default ".daidala" subdirectory is not applied, flip the "Inspecte repository" into "Apply default policy (checkin on main)" and proceed like with a new created working directory in a "new workflow". I thing we are doing a feature branch and an PR for approval the needed change" Continued: "the aspect was, if the user intent to inspect his "own" repository in order to apply it to a profile, for this repository is a PR opened in order to apply Daidala default policy -- not for Daidala itself" Continued: "it all about a UI feature that helps the user to add GitHub repositories that are not prepared for Daidala -- it's not about us in the development process"
**Affected capabilities:** CAP-0004, CAP-0006
**Created:** 2026-08-16

## Outcome

After inspect classifies a GitHub repository as `needs-bootstrap`, the same
row control becomes Apply default policy. Confirmed apply publishes
conservative `.daidala` policy on a non-default branch of the inspected
repository and opens one pull request there. The PR link stays on the row
after a Hermes restart until that repository is registered.

## Scope

- Flip the Config → GitHub Repositories inspect control after
  `needs-bootstrap`; keep digest-bound confirmation.
- After publishing the bootstrap branch, open one pull request on the
  inspected repository. Do not write the default branch, merge, register, or
  store a token.
- Persist the public PR URL in a profile-local receipt and project it from
  inventory until registration.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `.venv/bin/python -m pytest tests/test_dashboard_assets.py tests/test_repository_bootstrap.py tests/test_repository_registration.py tests/test_dashboard_api.py -q` |
| Closeout | in-progress | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check .` |

## Decisions

- Apply default policy is an operator UI for unprepared inspected repositories.
- The policy pull request belongs on the inspected repository. Confirmed apply
  calls host `gh pr create` after the bootstrap branch exists.
- The flipped row button is the sole apply authority. The preview panel keeps
  the confirmation checkbox.

## Evidence

- Focused dashboard/bootstrap suite passed after inspected-repo `gh pr create`.
- `python scripts/check_records.py .` and `python scripts/check_md_links.py .` passed.
