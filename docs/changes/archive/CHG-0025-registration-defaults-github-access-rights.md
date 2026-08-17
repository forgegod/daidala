# CHG-0025: Registration defaults GitHub access-rights help

**Status:** done
**Source request:** Direct operator request: "For the \"Registration defaults\" change the topic \"GitHub credentials\" to something that describes that the access rights are configured. Also the descriptions like \"Name of the process environment variable that already holds the read token, such as EXAMPLE_GITHUB_INTAKE_TOKEN. Uppercase letters, digits, and underscores only. Never GH_TOKEN, and never paste the token itself.\" should talk about \"GitHub token\", now which token classical or new? Which rights are at least mandatory? Describe this in detail."
**Affected capabilities:** CAP-0004
**Created:** 2026-08-17

## Outcome

The registration-defaults wizard names the GitHub group as configured access
rights and explains, in place, that each environment variable holds a GitHub
token, which token type to create, and the mandatory access rights.

## Scope

- Rename the defaults-wizard group from GitHub credentials to Configured
  GitHub access rights.
- Describe classic versus fine-grained GitHub tokens and the mandatory rights
  on the two environment-variable fields.
- Keep the same wording in the runbook, CAP-0004, dashboard contract, tests,
  and CAP-0004 wireframe.
- Do not change validation, preview/apply authority, or collect token values.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `.venv/bin/python -m pytest tests/test_dashboard_assets.py -q` exited 0 |
| Closeout | done | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check .` exited 0 |

## Decisions

- Intake stays a classic personal access token because fine-grained tokens
  cannot access user-owned GitHub Projects. Mandatory classic scopes are
  `read:project` and `read:org`.
- Findings stays a fine-grained personal access token restricted to the
  target repository. Mandatory repository permissions are Metadata read and
  Issues read and write.
- The form still stores only aliases and environment-variable names.

## Evidence

- Config wizard group title is Configured GitHub access rights.
- Intake and findings environment-variable help name GitHub token type and
  mandatory access rights.
- Runbook, CAP-0004, dashboard contract, asset tests, and CAP-0004 wireframe
  at 1440 × 1680 match that wording.
- Closeout gate passed: records, markdown links, lefthook, pytest, ruff.
