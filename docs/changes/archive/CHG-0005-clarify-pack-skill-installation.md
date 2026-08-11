# CHG-0005: Clarify pack skill installation state

**Status:** done
**Source request:** Direct operator request: "Is \"addyosmani\" now installed automatically? In my oppinion it was ok not to show the skill text if the skill is not installed, but I was missing this information in the UI that this skill need to be installed (2) because I was able to select the skill for a new workflow and the overview about all the skills where shown, my assumption was that the required skill was installed"
**Affected capabilities:** CAP-0003
**Created:** 2026-08-11

## Outcome

Start workflow and Config → Packs distinguish installed skills from selectable pack definitions without relying on an operator to infer readiness from generic blocked states or visible source text.

## Scope

- Remove display-only Addyosmani skill snapshots and serve external `SKILL.md` text only from installed skills.
- Label Start workflow pack options as ready, installation required, blocked, or readiness unavailable.
- Show explicit per-skill installation state and install targets in Config → Packs.
- Update focused service, dashboard, package-resource, capability, runbook, and DOX coverage.
- Keep release-content verification valid when an intentional tracked resource deletion is still unstaged.
- Keep the CAP wireframe unchanged because it depicts the primary Workflows frame, not Start workflow or Config → Packs.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | Pack/dashboard/install focused suite and isolated browser probe passed. |
| Closeout | done | Record, lint, pack, test, build, Twine, and release-content gates passed. |

## Decisions

- Pack definitions remain selectable for inspection, but selection never implies installed readiness.
- Uninstalled external skills expose install metadata and no `SKILL.md` content.
- Start workflow keeps non-ready packs visible and names installation as the required next action when the readiness check returns install actions.

## Evidence

- The focused pack, dashboard API/assets, and installation suite passed.
- The full suite passed: `685 passed in 23.12s`.
- Ruff, `node --check`, Lefthook, and `git diff --check` passed.
- Both Addyosmani and AI-DLC pack validation passed.
- Isolated browser QA showed `Installation required`, `not installed`, the exact install target, no source text, disabled workflow actions, and no runtime JavaScript errors on the corrected Config → Packs interaction.
- Build and Twine checks passed for the sdist and wheel.
- Release-content verification passed with `270 tracked file(s), 63 wheel member(s)`; its four focused tests include an intentional-deletion regression.
- Record validation passed with 3 capabilities, 5 change records, and 1 wireframe; Markdown-link validation passed for 88 files.
