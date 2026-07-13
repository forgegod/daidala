---
name: setup
description: Use when installing, checking, or starting Daidala for the first time. Guides explicit prerequisite discovery, previews the exact workflow request, and requires confirmation before mutation.
version: 0.2.0
author: Daidala
license: MIT
metadata:
  hermes:
    tags: [software-development, setup, onboarding, human-in-the-loop]
---

# Daidala Setup

## Overview

Guide a user from an installed Daidala plugin to one explicitly confirmed
workflow start. Setup prepares and starts; `daidala:orchestrate` remains the
worker contract. This skill works without the web dashboard and uses the same
`daidala_start` request in dashboard and non-dashboard sessions.

## When to Use

Load this skill explicitly as `daidala:setup` when the user wants to install,
check, configure, or start Daidala. Do not use it for stage execution or for
resuming an already-created workflow.

## Procedure

1. Check the active Hermes version, Daidala plugin state, gateway or dispatcher
   availability, selected pack, exact required skills, available profiles, and
   named Kanban boards. Use documented Hermes surfaces and
   `daidala_pack_info`; do not inspect private databases or infer names.
2. Present missing prerequisites with exact commands or tool calls. Installation,
   board creation, pack setup, and other mutations require a separate preview and
   explicit confirmation before execution. Never request or display credentials.
3. Ask the user to select an existing named board. Offer explicit board creation
   only through the documented Hermes Kanban operation. If creation is declined,
   keep setup read-only.
4. Ask for one default existing profile for every executable stage. Show the
   complete mapping and ask only for explicit overrides of `define`, `plan`,
   `implement`, `verify`, `review`, or `deliver`.
5. Ask for the pack, absolute target repository, stable workflow ID, and complete
   goal. Do not infer a path from prose or generate an unstable identifier.
6. Ask the user to choose exactly one policy source: no constraints; explicit
   validated YAML content; or an exact installed policy skill plus its verified
   complete-directory SHA-256 digest. Never infer a policy source.
7. Build and display the exact request below. Validate required fields and show
   the selected board, pack, repository, workflow ID, full stage-profile map,
   and constraint provenance. Do not call `daidala_start` yet.
8. Ask the user to explicitly confirm that exact preview. A general request to
   configure Daidala is not confirmation. If the preview changes, show it again
   and obtain fresh confirmation.
9. After confirmation, call `daidala_start` exactly once. Report the returned
   workflow and card identities and point the user to native Kanban. If the
   dashboard is available, `/daidala` is an optional observation surface; its
   absence never changes the request or blocks setup.
10. Stop after start. Hermes Kanban dispatches workers using
    `daidala:orchestrate`; setup does not execute lifecycle stages.

## Exact Start Request

Use only the current `daidala_start` argument names:

- `board_slug`: selected existing board;
- `target_repository`: absolute clean local Git checkout;
- `goal`: complete development goal;
- `stage_profiles`: object with exactly `define`, `plan`, `implement`, `verify`,
  `review`, and `deliver`, each mapped to an existing profile;
- `pack`: selected bundled pack;
- `workflow_id`: explicit stable identifier;
- optional `constraints_content`; or optional `constraints_skill` together with
  `constraints_skill_digest`.

`constraints_content` and `constraints_skill` are mutually exclusive. A
`constraints_skill_digest` without `constraints_skill` is invalid. Do not add
aliases, omit executable stages, or translate this request into a second setup
schema.

## Common Pitfalls

- Starting before the exact preview receives explicit confirmation.
- Treating a missing dashboard as a setup failure.
- Guessing board, profile, repository, workflow ID, or policy source.
- Using `--profile` as Daidala's default-profile input; it is a Hermes host
  option. The CLI uses `--default-profile` and optional `--stage-profile`.
- Installing skills or creating boards without a separate mutation preview.
- Starting stage work in the setup session instead of leaving it to Kanban.
- Copying pack lifecycle data instead of calling `daidala_pack_info`.

## Verification Checklist

- [ ] Supported Hermes and enabled Daidala plugin checked.
- [ ] Pack and exact required skills checked.
- [ ] Existing board and profiles selected explicitly.
- [ ] Absolute repository, stable workflow ID, goal, and policy source explicit.
- [ ] Preview contains the complete current `daidala_start` request.
- [ ] Human explicitly confirmed the unchanged preview.
- [ ] `daidala_start` called exactly once after confirmation.
- [ ] Dashboard availability did not alter the request.
- [ ] Setup stopped after returning workflow and card identities.
