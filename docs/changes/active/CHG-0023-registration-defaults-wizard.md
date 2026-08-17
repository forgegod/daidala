# CHG-0023: Registration defaults wizard and checker

**Status:** in-progress
**Source request:** Direct operator request: "(1) Do we have a documentation where this details together with an example as explained here? If not do it, but do not reference to a specific repository like durchsieben.de in the expleneation. Keep it general purpose. (2) Because it's hard to remember and the users are not experts, I would like to have a wizzard with this example that helps the user to create, save and edit the file. There should also be a validator checker for this file. This can be prepared with the phased-plan-design skill if you want"
**Affected capabilities:** CAP-0004
**Created:** 2026-08-17

## Outcome

Operators can create, validate, edit, and save profile-local
`repository-registration-defaults.yaml` through a guided CLI and Config
wizard, with the same deterministic checker. The file remains profile
authority: aliases and environment-variable names, never token values.

## Scope

- Keep the operator example in `docs/07-runbook.md` current.
- Add a preview/confirm CLI checker and apply path for the defaults file.
- Add a Config wizard that uses that same service.
- Optionally seed a missing file from an existing registration on the same
  profile. Do not invent destinations or aliases.

## Phases

Mark a phase `in-progress` while running it, `done` once its gate passes
(record evidence), `pending` otherwise.

| Phase | Status | Verification gate |
|---|---|---|
| 0. Operator example | done | `python scripts/check_md_links.py .` and `python scripts/check_records.py .` pass after the runbook example exists |
| 1. CLI validate / preview / apply | done | `.venv/bin/python -m pytest tests/test_repository_registration.py tests/test_cli.py -q` exited 0 (93 tests); `ruff check` on the changed Python files passed |
| 2. Config wizard | pending | `.venv/bin/python -m pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py -q` exits 0; CAP-0004 and dashboard AGENTS describe the wizard |
| 3. Closeout | pending | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check .` |

## Phase 0 — Operator example

**Goal:** A general-purpose example and field rules exist in the runbook.

Steps:

1. Document `$HERMES_HOME/repository-registration-defaults.yaml` in
   `docs/07-runbook.md#configure-registration-defaults`.
2. Use synthetic aliases, variable names, and destination only.
3. Index the section from `docs/README.md` and CAP-0004.

**Verification gate:** record and markdown-link checks pass.

## Phase 1 — CLI validate / preview / apply

**Goal:** Operators can check and write the file without a dashboard.

Steps:

1. Expose `parse_registration_defaults` through a `daidala project defaults`
   preview/apply command.
2. Preview is dry-run: path-free validity, field errors, and a digest.
3. Apply requires the digest and literal confirmation. It writes mode `0600`
   only under the resolved profile data root.
4. If the profile already has one registration, preview may offer to seed
   from that record. It must not invent missing destination or aliases.

**Verification gate:** focused registration and CLI tests exit 0.

## Phase 2 — Config wizard

**Goal:** Config → GitHub Repositories offers create/edit/validate for the
selected profile's defaults file.

Steps:

1. Update dashboard AGENTS and CAP-0004: the wizard may collect aliases,
   environment-variable names, maintainers, destination, and limits. It must
   never collect token values or return them.
2. Preview/apply routes reuse the Phase 1 service, digest, and confirmation.
3. Missing or invalid defaults show the wizard instead of only a blocked
   inspect reason.
4. Add a CAP-linked wizard wireframe in the same slice as the runtime UI.

**Verification gate:** dashboard API/asset tests exit 0; CAP-0004 matches
the shipped wizard.

## Phase 3 — Closeout

**Goal:** Records, links, and the repository gate match the shipped wizard.

**Verification gate:** full closeout command in the phase table.

## Decisions

- This CHG is the implementation plan. Do not add a competing `docs/plans/`
  file.
- Browser payloads still must not carry token values. Aliases, environment
  variable names, and the attended destination are the wizard's inputs
  because they already live in the profile-local defaults file.
- Seeding from an existing same-profile registration is allowed. Inferring
  a destination from Hermes home or chat context is not.
- Do not write the defaults file from inspect or bootstrap apply.

## Evidence

- Phase 0: operator example added to `docs/07-runbook.md`.
- Phase 1: `daidala project defaults` preview/apply plus seed-from-one-registration; 93 focused tests passed.
