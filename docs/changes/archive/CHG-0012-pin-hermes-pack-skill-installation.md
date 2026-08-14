# CHG-0012: Pin Hermes pack skill installation

**Status:** done
**Source request:** Direct operator request: "Trying to install the addyosmani skills (https://github.com/addyosmani/agent-skills @ 7ce442de03ddc1b72480c3b48d55c62880ea2a90) but getting digest missmatch"; approval: "approved"; installation clarification: "The installation of skill should be done with hermes not a second tool. Also the digest checks should only relay on the supported files during the installation"; follow-up: "the digest mismatch should only be a warning but not a showstopper to install a skill -- this should not prevent to use daidala"; selection clarification: preserve the original `7ce442d` baseline and transplant only the self-contained-reference changes; selecting a skill must move the view to its information/install box.
**Affected capabilities:** CAP-0003
**Created:** 2026-08-14

## Outcome

An operator can install Addyosmani skills through Hermes from the exact declared
Git revision. Daidala reports installed-bundle digest differences as warnings
without blocking installation or workflow start, and skill selection moves focus
and the viewport to the actionable information panel.

## Scope

- Keep Hermes as the sole external-skill mutation boundary.
- Resolve compact GitHub skill declarations to immutable raw `SKILL.md` URLs at the pack's declared revision.
- Pin readiness to the canonical installed bundle produced by Hermes, not files present only in the source directory.
- Pin the pack to a fork commit based on the requested upstream revision, with
  support files co-located under their owning skills and scanner-sensitive
  examples rewritten without weakening their safety guidance.
- Recompute every declared Addyosmani digest from the corresponding
  Hermes-installed bundle.
- Treat installed-bundle digest mismatch as advisory while preserving missing and
  disabled exact-name blockers.
- Focus and scroll Config → Packs to the selected skill information/install panel.
- Update focused tests, CAP-0003, pack contracts, and owning DOX contracts.
- Exclude recursive installation, alternate installers, moving branch targets,
  and silent skill updates.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Approval boundary | done | Direct operator approval and Hermes-only clarification recorded above. |
| Pinned installation vertical slice | done | Focused pack, service, CLI, installation, workflow-preflight, and dashboard-asset tests pass. |
| Integration | done | Isolated Hermes apply installs and readies all 20 declared skills at the pinned fork revision; the full repository gate passes. |
| Closeout | done | CAP, durable contracts, DOX, and final evidence are current; CHG is archived. |

## Decisions

- Use only `hermes skills install`; do not add `npx skills` or another installer.
- Derive immutable raw GitHub URLs from `source`, `source_revision`, and each compact install declaration so pack YAML remains source-kind data rather than shell syntax.
- Treat `content_digest` as the comparison digest of the complete installed directory that Hermes produces. Upstream files unsupported by Hermes installation are outside that comparison identity.
- Base `forgegod/addyosmani-agent-skills@8a63e3bfb6da979e5073939e1c4458ad99b93c83`
  on the requested `7ce442de03ddc1b72480c3b48d55c62880ea2a90`
  revision. Keep support files inside each isolated skill bundle and retain the
  fork's validator for missing or escaping reference links.
- Require installation post-verification to observe the declared exact name.
  Preserve digest mismatch in `revision_mismatches`, but do not add a blocker,
  fail a successful install action, or reject workflow start.
- Move keyboard focus and the viewport only after the selected skill document or
  installation metadata has rendered.

## Evidence

- Hermes 0.20.0 reproduced the mismatch: the declared `idea-refine` source directory hashes to `c999f1db…`, while Hermes installs its supported `SKILL.md` bundle with digest `d134901c…`.
- The unpinned Hub target resolved current upstream commit `be42637c…` instead of declared revision `7ce442de…`; immutable raw URLs at the declared revision resolve the source drift.
- Independent review found inconsistent compact/raw `install_target` projections
  and unsafe relative path segments; both now have regression coverage.
- The original isolated pack apply installed 7 of 20 skills and exposed missing
  support files plus scanner false positives in the remaining bundles. The fork
  co-locates those files, validates all 24 source skills, and removes direct host
  configuration or secret-like examples while retaining the guidance.
- Final isolated `daidala packs install addyosmani --apply` through Hermes 0.20.0
  installed and readied all 20 declared skills from revision
  `8a63e3bfb6da979e5073939e1c4458ad99b93c83`, with zero failed actions and zero
  digest warnings.
- A headless Chromium probe confirmed that clicking a skill scrolls and moves
  keyboard focus to `daidala-skill-content`, renders the information/install
  panel, and shows digest drift as `Ready with warnings`.
- Focused verification passes for pack validation, pack service, installation,
  workflow preflight, and dashboard asset behavior.
- The repository gate passes with 748 tests, Ruff, Lefthook, both pack
  validations, record and Markdown-link checks, package build, Twine checks, and
  release-content verification.
