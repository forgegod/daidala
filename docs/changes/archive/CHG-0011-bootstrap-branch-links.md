# CHG-0011: Bootstrap branch naming and operator GitHub links

**Status:** done
**Source request:** Direct operator request: "For the default branch name use the Conventional Commits Spec https://www.conventionalcommits.org/ naming schema. Because the branch is pushed, offer also a online link to the repository branch and `.daidala` subdirectory for convinience; is there also an ability to merge the branch to main via browser/url? if this is the case, offer also this link to make the merge; if it would be better ot make a pull-request in order to simplify the merge, considner this -- push back if there is a better approach that matches the architecture of Daidala"
**Affected capabilities:** CAP-0003, CAP-0006
**Created:** 2026-08-14

## Outcome

Bootstrap publishes policy on a Conventional Commits–style branch name and returns
path-free GitHub convenience links for the branch, the `.daidala` tree on that
branch, and GitHub’s compare/open-pull-request page. Daidala still does not create
PRs, merge, or update the default branch.

## Scope

- Rename the bootstrap target branch to `chore/daidala-bootstrap-project-policy`.
- Add public `links` on bootstrap preview/apply: `branch`, `daidala_tree`,
  `compare_pull_request` (GitHub compare with `expand=1`).
- Surface those links in dashboard bootstrap UI and CLI JSON; update CAP-0006,
  runbook, wireframe, and tests.
- Do not add GitHub API PR create/merge, default-branch push, or registration writes.

## Decisions

- Conventional Commits defines commit-message types; branch naming follows the
  common `type/description` convention with type `chore` because bootstrap adds
  tooling/policy scaffolding, not product feature work.
- Prefer a compare/open-PR **link** over Daidala-created PRs. Creating or merging
  PRs would reopen authority excluded by CAP-0005/CHG-0009; a browser link keeps
  merge as an operator action on GitHub.
- There is no reliable one-click merge URL that bypasses PR/review for protected
  default branches. The compare/open-PR page is the correct GitHub browser path.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | Focused bootstrap/assets tests + CAP/runbook/wireframe update; pytest and ruff on touched paths; records and link checks. |
| Closeout | done | Focused gates passed; CHG archived. |

## Evidence

- Branch constant is `chore/daidala-bootstrap-project-policy`.
- Preview/apply JSON includes `links.branch`, `links.daidala_tree`, and
  `links.compare_pull_request`; `writes.pull_request` remains false.
- Dashboard surfaces the three operator links; CAP-0006 and runbook updated.
- Focused pytest (`tests/test_repository_bootstrap.py`,
  `tests/test_dashboard_assets.py`), ruff, records, markdown links, and CAP-0006
  wireframe render passed.
