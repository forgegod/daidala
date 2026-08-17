# CHG-0022: Flip inspect to Apply default policy

**Status:** in-progress
**Source request:** Direct operator request: "if in the "GitHub Repositories" a repository is inspected where the default ".daidala" subdirectory is not applied, flip the "Inspecte repository" into "Apply default policy (checkin on main)" and proceed like with a new created working directory in a "new workflow". I thing we are doing a feature branch and an PR for approval the needed change" Continued: "the aspect was, if the user intent to inspect his "own" repository in order to apply it to a profile, for this repository is a PR opened in order to apply Daidala default policy -- not for Daidala itself" Continued: "it all about a UI feature that helps the user to add GitHub repositories that are not prepared for Daidala -- it's not about us in the development process" Continued: "My expectation was that in the situation where a github repository is inspected and do not have the default policy applied, the UI offer me to create a PR for this repo with the required changes so the user is able to apply the patch. Also a link to the PR is offered so the user can easily accomplish this task. The PR link should be persitent for hermes dashboard restarts. The user can delete this information [x] if it is not required anymore for him. A PR merge&push check while oppening the "GitHub Repository" tab in "Configuration" would be a nice feature"
**Affected capabilities:** CAP-0004, CAP-0006
**Created:** 2026-08-16

## Outcome

After inspect classifies a GitHub repository as `needs-bootstrap`, the same
row control becomes Apply default policy. Confirmed apply publishes
conservative `.daidala` policy on a non-default branch of the inspected
repository and opens one pull request there. The PR link stays on the row
after a Hermes restart until the operator dismisses it or registers the
repository. Opening Config → GitHub Repositories refreshes whether that PR
is open, merged, or closed. Inspect of a repository that already has
committed policy does not offer a bootstrap PR; missing profile registration
defaults is reported as a registration-block, not a missing-policy offer.

## Scope

- Flip the Config → GitHub Repositories inspect control after
  `needs-bootstrap`; keep digest-bound confirmation.
- After publishing the bootstrap branch, open one pull request on the
  inspected repository. Do not write the default branch, merge, register, or
  store a token.
- Persist the public PR URL in a profile-local receipt and project it from
  inventory until registration or explicit dismiss.
- Inventory refresh reports public PR merge state. The row offers a dismiss
  control that deletes only the local receipt.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | in-progress | `.venv/bin/python -m pytest tests/test_dashboard_assets.py tests/test_repository_bootstrap.py tests/test_repository_registration.py tests/test_dashboard_api.py -q` |
| Closeout | pending | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check .` |

## Decisions

- Apply default policy is an operator UI for unprepared inspected repositories
  that lack committed `.daidala/project.yaml`.
- The policy pull request belongs on the inspected repository. Confirmed apply
  calls host `gh pr create` after the bootstrap branch exists.
- A profile-local receipt is dismissible. Dismiss does not close the GitHub PR.
- Inventory GET may query host `gh` only for pending bootstrap receipts.

## Evidence

- Focused dashboard/bootstrap/registration suite passed after dismiss and merge-state refresh.
- `python scripts/check_records.py .` and `python scripts/check_md_links.py .` passed.
