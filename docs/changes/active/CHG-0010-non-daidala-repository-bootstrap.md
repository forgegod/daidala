# CHG-0010: Non-Daidala repository bootstrap and policy check-in

**Status:** in-progress
**Source request:** Direct operator request: "Based on the analysis the user should have the ability to use a non-daidala repository for the initial setup. Daidala should then integrate daidala as the initial workflow with an checkin. If there are any inconsistencies with this approach, push back with an better suggestion"
**Affected capabilities:** CAP-0003, CAP-0004
**Created:** 2026-08-14
**Depends on:** CHG-0009 closeout should finish or remain non-conflicting; this CHG must not reopen delivery/PR scope rejected in CHG-0009 without explicit amendment.

## Outcome

An operator who pastes a GitHub.com repository that has no committed
`.daidala/project.yaml` can complete a preview-confirmed **bootstrap** that
checks in conservative Daidala policy on a non-default branch, merge that branch
outside Daidala, then run the existing CAP-0004 registration path against the
default-branch manifest. Config → GitHub Repositories never dead-ends on a
generic 409 for a readable public repository that simply lacks policy.

## Pushback (why not the literal request)

The request collapses three different authorities into one step. That is
inconsistent with shipped contracts:

1. **Registration cannot invent repository policy.** CAP-0004 and
   `RepositoryRegistrationService.preview` bind controller registration to the
   *committed* `.daidala/project.yaml` identity, allowed remotes, packs,
   verification, mutation bounds, and release flags
   (`daidala/repository_registration.py`). Writing profile-local registration
   for a repo with no committed manifest would make the controller claim policy
   the repository never agreed to.
2. **A pack workflow cannot be the first bootstrap mechanism.** Start, plan
   admission, review, and CAP-0005 delivery all assume a trusted registration,
   checkout identity, packs, and usually an accepted review. Using Addyosmani /
   AI-DLC as the vehicle to *create* `.daidala/**` is circular and forces LLM
   judgment where the product needs a deterministic template.
3. **Registration and delivery stay separate.** CHG-0009 decided that
   registering a repository never grants commit/push authority and that V1
   delivery never updates the default branch, opens a PR, merges, or publishes.
   Auto-check-in to `main` during “register” would violate that boundary.
4. **“Initial workflow with a check-in” is the right operator story, wrong
   mechanism if it means one Start-workflow button.** The observable outcome
   (non-Daidala repo → Daidala policy on the remote → register → real workflows)
   stands. The implementation must be a **pre-registration bootstrap** plus the
   existing registration path, not a fake registration or a full pack graph.

### Recommended product shape

```text
Inspect URL
  ├─ inaccessible / invalid URL          → named blocked state
  ├─ already registered for profile      → named duplicate state
  ├─ committed valid project.yaml        → CAP-0004 register preview (unchanged)
  └─ readable repo, missing/invalid yaml → bootstrap preview (this CHG)
        → confirm bootstrap check-in to branch daidala/bootstrap
        → operator merges to default branch outside Daidala
        → re-inspect → CAP-0004 register
        → later Start workflow / delivery under normal gates
```

Bootstrap is deterministic Python: generate strict policy files, open or reuse an
owned checkout, commit only those files on a derived non-default branch, push
that branch under explicit confirmation. It is **not** registration, **not**
plan approval, and **not** CAP-0005 reviewed delivery of an implementation diff.

## Current state

- Inspect of `https://github.com/forgegod/durchsieben.de` under
  `daidala-dashboard` fails because the default branch has no
  `.daidala/project.yaml` (GitHub Contents 404). CLI truth:
  `GitHub repository manifest is unavailable through the host authentication`.
- Dashboard `POST /repository-registration/preview` maps almost every
  `RepositoryRegistrationError` to generic
  `repository registration preview unavailable` (`dashboard/plugin_api.py`),
  hiding the classify signal operators need.
- CAP-0004 registration still requires profile-local
  `repository-registration-defaults.yaml`; bootstrap does not create that file.
- CAP-0005 delivery requires accepted review, trusted registration, release
  flags true, and owned worktree evidence — unusable for first-time policy
  introduction.
- Strict manifest schema is `daidala.project/v1` with exact pack pins, suites,
  mutation paths, and release booleans (`daidala/projects.py`). Bootstrap must
  emit a parseable full manifest, not a partial stub.

## Risk call-out

- **Remote write.** Bootstrap push can create a branch on a customer repository.
  Safety net: preview-only default; apply requires exact preview digest and
  literal confirmation token `bootstrap-repository`; never updates default
  branch, never force-pushes, never opens/merges PRs in V1.
- **Policy too loose.** A generated manifest with broad `mutable_paths` or
  `allow_commit`/`allow_push: true` would over-grant after merge. Safety net:
  bootstrap templates are conservative (`release.*: false`, protected
  `.daidala/project.yaml`, narrow mutable globs, pinned pack digests from the
  running Daidala install). Operators edit policy in a later normal workflow.
- **Authority confusion.** If bootstrap also wrote registration, a failed merge
  would leave the controller bound to unmerged policy. Safety net: bootstrap
  never writes registration or credential-bindings; registration remains
  CAP-0004 after default-branch revalidation.
- **Credential path.** Registration-time delivery bindings do not exist yet.
  Safety net: V1 bootstrap push uses the same host GitHub CLI authentication
  already required for inspect (`gh`), in a credential-minimal child
  environment, and surfaces only boolean readiness — not the delivery-PAT path
  from CAP-0005. Document that host `gh` must be allowed to create the branch;
  do not invent a second secret UX in the browser.

## Scope

- Add a deterministic repository **classify + bootstrap** service shared by CLI
  and dashboard (no nested `hermes chat`, no MCP/HTTP daemon).
- Extend Config → GitHub Repositories and `daidala project` CLI so a missing
  committed manifest becomes an explicit **bootstrap** path with preview of the
  exact files and target branch, then digest-bound apply.
- Generate at least `.daidala/project.yaml` and the referenced default
  constraints file; keep contents strict-YAML, path-bounded, and digestable.
- After a successful bootstrap push, instruct re-inspect/register; do not
  auto-register.
- Amend CAP-0004 only for classify/error surfacing that remains registration
  behavior. During the bootstrap vertical slice, create new capability
  CAP-0006 (repository policy bootstrap) with HTML/PNG wireframe and add it to
  the product index; then add CAP-0006 to this CHG’s affected-capabilities
  field in the same change.
- Tests: unit service, CLI parity, dashboard API/assets, fail-closed cases.
- Operator docs: runbook onboarding path for non-Daidala repos.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Approval boundary | done (direct operator approval: "Approve CHG-0010") | Direct operator approval of this CHG’s pushback, two-stage onboard shape, host-`gh` bootstrap push, non-default branch only, and no auto-register. |
| Classify + error surfacing | done (focused pytest + ruff on registration/CLI/dashboard paths) | Focused tests prove missing-manifest inspect returns a stable `needs-bootstrap` (or equivalent) classification; dashboard/CLI no longer show only generic preview-unavailable for that case; `pytest` on touched tests and `ruff check` on touched paths exit 0. |
| Bootstrap preview/apply vertical slice | in-progress | Service+CLI+dashboard bootstrap preview/apply with digest+literal confirm; fake `gh`/git boundary proves branch-only check-in of generated policy files, rejects default-branch target and stale digest; no registration files written; CAP-0006 + wireframe + CAP-0004 classify note + runbook section present; focused pytest + `python scripts/check_records.py .` + `python scripts/check_md_links.py .` exit 0. |
| Closeout | pending | Full repository gate: `python scripts/check_records.py .`; `python scripts/check_md_links.py .`; `lefthook validate`; `pytest`; `ruff check .`; both pack validations; `python -m build`; `python -m twine check dist/*`; `python scripts/check_release_contents.py . --wheel dist/*.whl`. |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate
passes, `pending` otherwise. Keep exactly one `in-progress` phase while the CHG
status is `in-progress`.

## Phase 0 — Approval boundary

**Goal:** Lock the product fork before code changes.

Steps:

1. Operator reviews Pushback and Recommended product shape in this CHG.
2. Confirm or amend: host-`gh` for bootstrap push V1; branch name scheme;
   generated-file set; no PR/merge automation; no auto-register.
3. On approval, set CHG status to `in-progress` and Phase 0 to
   `done (direct operator approval: …)`; then start Phase 1.

**Verification gate:** Direct operator approval recorded in Evidence.

## Phase 1 — Classify + error surfacing

**Goal:** Make non-Daidala repos diagnosable without granting new write authority.

Steps:

1. Introduce a pure classification result for one GitHub URL + profile, covering
   at least: invalid URL, host auth/metadata failure, needs-bootstrap
   (missing/invalid manifest), identity mismatch, already registered,
   registerable preview payload.
2. Keep CAP-0004 register preview behavior for the registerable case; do not
   weaken manifest requirements.
3. Dashboard/CLI: map classification to operator-visible states and next actions
   (`Bootstrap Daidala policy` vs `Register repository`). Stop collapsing
   path-free service errors into a single generic 409 where a stable public
   reason already exists.
4. Tests for classification and dashboard/CLI projection.

**Verification gate:** Focused pytest + ruff on touched paths exit 0; missing
manifest no longer presents only generic preview-unavailable.

## Phase 2 — Bootstrap preview/apply vertical slice

**Goal:** Check in conservative Daidala policy on a non-default branch for one
profile-selected repository, without registration.

Steps:

1. Deterministic template builder: from GitHub canonical identity + running pack
   pins, emit strict `.daidala/project.yaml` and default constraints content.
   Defaults: `release.allow_commit/push/publish: false`; protect
   `.daidala/project.yaml`; narrow mutable paths; pin pack
   revision/digest from installed Daidala resources (same source of truth as
   pack validation).
2. `RepositoryBootstrapService.preview` / `apply` with digest binding to profile,
   canonical repo, file digests, and target branch (derived, e.g.
   `daidala/bootstrap` or `daidala/bootstrap-<short-digest>`). Confirmation token
   `bootstrap-repository`.
3. Apply: ensure owned checkout under checkout-root policy; create/update only
   bootstrap files; commit; push branch via host `gh`/git boundary; return
   path-free branch/commit receipt. Fail closed on dirty conflicting paths,
   existing divergent remote branch content mismatch (define exact rule in
   implementation: reject if remote branch exists with different tree), or
   default-branch name collision.
4. Explicitly do **not** write `projects/*/registration.yaml` or credential
   bindings. Response next-step: merge branch on GitHub, then CAP-0004 register.
5. CLI: `daidala project bootstrap --github-url … --profile …` preview/apply.
6. Dashboard: bootstrap confirm UI on Config → GitHub Repositories.
7. CAP-0006 implemented + HTML/PNG wireframe; CAP-0003/0004 links; runbook
   section; security note that bootstrap push is host-`gh` and branch-only.

**Verification gate:** Focused service/CLI/dashboard tests, records and link
checks exit 0; CAP-0006 present with runtime+test evidence.

## Phase 3 — Closeout

**Goal:** Leave repository truth consistent and CHG archiveable.

Steps:

1. Full repository/release gate.
2. Confirm no auto-register, no default-branch push, no token browser input.
3. Mark CHG `done` and move to `docs/changes/archive/`.

**Verification gate:** Full gate commands in the phase table exit 0.

## Decisions

- **Two-stage onboard, not register-without-manifest.** Bootstrap introduces
  committed policy; registration continues to require default-branch policy.
- **Deterministic bootstrap, not pack workflow.** First check-in is template
  generation + git branch publish; LLM packs start only after registration.
- **Branch-only check-in.** V1 never updates the repository default branch and
  never opens/merges pull requests (unchanged CHG-0009 exclusion).
- **No auto-register after bootstrap.** Merge remains a human GitHub action;
  registration re-fetches and revalidates.
- **Host `gh` for bootstrap push V1.** Avoid depending on CAP-0005 delivery
  registration bindings that do not exist yet; keep browser free of tokens.
- **Conservative generated policy.** Release flags false until a later attended
  policy change lands on the default branch.
- **Progress authority is this CHG.** No profile-private plan and no new
  `docs/plans/` entry for this work.

## Evidence

- Operator trigger: Config → GitHub Repositories inspect of
  `forgegod/durchsieben.de` returned
  `409: {"detail":"repository registration preview unavailable"}` while CLI
  reported missing manifest through host authentication.
- Direct operator approval: "Approve CHG-0010".
- Phase 1 classify vertical slice: `RepositoryRegistrationService.classify`
  returns path-free `needs-bootstrap` for missing `.daidala/project.yaml`;
  dashboard/CLI surfaces that classification instead of a generic preview-
  unavailable 409; CAP-0004 documents the classify contract. Focused pytest on
  `tests/test_repository_registration.py`, `tests/test_cli.py`,
  `tests/test_dashboard_api.py`, and `tests/test_dashboard_assets.py` plus ruff
  on touched paths passed.
- Related shipped contracts: CAP-0004, CAP-0005, CHG-0009 decisions on
  registration vs delivery separation.

## Out of scope

- Auto-merge or default-branch commit of bootstrap files.
- Pull request creation UI or GitHub App installation.
- Treating bootstrap as Start workflow / plan admission / attended review.
- Creating or editing `repository-registration-defaults.yaml` from the browser.
- Password-manager integration or browser token entry.
- Registering against a non-default bootstrap branch without merge.
- Multi-forge support beyond GitHub.com.
- Changing CAP-0005 delivery branch naming or review gates.
- Completing CHG-0009 closeout (separate residual human review).
