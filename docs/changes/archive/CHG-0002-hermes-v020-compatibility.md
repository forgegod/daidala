# CHG-0002: Admit Hermes v0.20.0

**Status:** done
**Source request:** Direct operator request: "there is a new hermes version v0.20.0 we have to evaluate the implementation against so we can upgrade to latest hermes agent afterwards"
**Affected capabilities:** CAP-0001, CAP-0002, CAP-0003
**Created:** 2026-08-10

## Outcome

Daidala admits the exact Hermes v0.20.0 release as a supported host only after its entry-point plugin, directory plugin, Kanban, profile, dashboard, cron, pack, build, and release-matrix boundaries pass deterministic verification. The production Hermes upgrade remains outside this change and requires a separate attended operator action after compatibility closes.

## Scope

- Pin Hermes semantic version `0.20.0`, build `2026.8.3`, tag `v2026.8.3`, and revision `3c27eb6234bf91b8ceee9e9071591b31e9b148cb` in the release support matrix.
- Install the exact Hermes v0.20.0 source checkout in editable mode because it rejects wheel builds, while retaining the existing pinned installation path for older hosts and installing the Daidala wheel without dependency resolution.
- Run the Hermes dashboard build under Node.js 26 as required by the v0.20.0 release.
- Correct the support-matrix dashboard evidence validator to consume the probe's current literal-confirmation fields.
- Widen both bundled workflow-pack constraints from `<0.20.0` to `<0.21.0` and update focused tests and integration documentation.
- Preserve live platform delivery as an attended post-upgrade check; automated compatibility uses isolated homes and does not send external messages.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Compatibility evaluation | done | Exact-host core, entry-point plugin, directory plugin, dashboard, cron, pack, source-build, and repository checks recorded below. |
| Compatibility vertical slice | done | Focused probe, support-matrix, pack, workflow, and documentation tests pass against exact v0.20.0 identity. |
| Closeout | done | Full repository verification passes, current support documentation is updated, and the CHG is archived. |

## Decisions

- The operator approved this recorded scope with `proceed with CHG-0002`.
- The exact immutable tag revision is authoritative; a mutable branch or release-page target field is not accepted as host identity.
- Hermes v0.20.0 keeps the Python plugin contracts Daidala uses: `register(ctx)`, `register_tool`, `register_skill`, `register_cli_command`, JSON-string tool handlers, and both entry-point and directory discovery passed unchanged.
- The upper bound remains a closed next-minor boundary. This evaluation supports `0.20.x`; it does not claim forward compatibility with `0.21.0`.
- No CAP outcome changes are proposed. This is host-compatibility maintenance for the existing three capabilities; [`docs/08-hermes-integration.md`](../../08-hermes-integration.md) remains the detailed support-contract owner.
- Node.js 22.23.2 also built the v0.20.0 dashboard source successfully, but the release explicitly requires Node.js 26 for installers, heal, and upgrade. Release verification will therefore use Node.js 26.

## Evidence

### Authoritative upstream identity and changes

- [Hermes Agent v0.20.0 release](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.3) identifies semantic version `0.20.0`, release build `2026.8.3`, a Node.js 26 runtime requirement, and retirement of pip/PyPI wheel installation for Hermes itself.
- [Exact v2026.8.3 source](https://github.com/NousResearch/hermes-agent/tree/3c27eb6234bf91b8ceee9e9071591b31e9b148cb) resolves to revision `3c27eb6234bf91b8ceee9e9071591b31e9b148cb`.
- [v0.19.0-to-v0.20.0 comparison](https://github.com/NousResearch/hermes-agent/compare/v2026.7.20...v2026.8.3) was reviewed for Daidala's plugin, Kanban, profile, cron, send, dashboard, and installation boundaries.
- The official [installation](https://hermes-agent.nousresearch.com/docs/getting-started/installation), [plugin](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins), [Kanban](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban), and [cron](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron) contracts were cross-checked against the exact tag source.
- `uv pip install --python /tmp/hermes-v0200-venv/bin/python /tmp/daidala-hermes-v0.20.0` failed as designed because v0.20.0's `setup.py` rejects wheel builds. Installing that exact checkout with `--editable` succeeded and reported `hermes-agent 0.20.0 (build 2026.8.3)`.

### Compatibility execution

- `scripts/probe_hermes_compatibility.py` passed twice against the exact host. It exercised version/build/revision identity, `--help`, isolated-home initialization, profile listing and selection, Kanban board/card CRUD and transitions, worker context, one-shot worker execution, 8,192-character card bodies, and dashboard CLI parsing.
- `scripts/probe_hermes_plugin_compatibility.py` passed twice for the installed `hermes_cli.plugins` entry point and twice with entry-point metadata disabled for directory discovery. Both modes loaded 22 Daidala tools, 8 bundled skills, both workflow packs, and the `daidala` native CLI.
- `scripts/probe_hermes_dashboard_compatibility.py` passed twice against isolated dashboards. Backend manifest, SDK `1.1.0`, profile routing, board/task APIs, project/cycle APIs, literal-confirmation refusal, and preview readiness all remained compatible.
- An isolated v0.20.0 cron lifecycle created, edited, and removed the script-only `daidala-artifact-curator` job. The CLI retained the `Created job: <12-hex-id>` and `Updated job: <12-hex-id>` receipts consumed by `CuratorCron`.
- The exact dashboard source completed `npm ci --workspace web` and `npm run build -w web` under Node.js 26. It also completed under Node.js 22.23.2, confirming source compatibility even though release CI now follows v0.20.0's Node.js 26 requirement.
- Before implementation, `daidala packs check addyosmani` and `daidala packs check aidlc` correctly rejected the v0.20.0 host because both manifests declared `<0.20.0`. Both packs now declare `>=0.18.2,<0.21.0`, and their exact new content digests are pinned in `.daidala/project.yaml`.

### Resolved repository blockers

- `scripts/run_hermes_support_matrix.py` now validates `preview_readiness_status: 409`, `unconfirmed_start_status: 400`, and unchanged setup state. Regression coverage accepts the current schema and rejects the stale `preview_confirmed` shape.
- `.github/workflows/release.yml` now pins the exact v0.20.0 source, installs that host editable, builds all three supported dashboards under Node.js 26, and executes one two-repetition matrix across v0.18.2, v0.19.0, and v0.20.0.
- Probe defaults, dashboard support projection, both workflow packs, the strict project pack digests, tests, and current operator documentation now agree on exact v0.20.0 support within `>=0.18.2,<0.21.0`.

### Repository verification

- The final release wheel `dist/daidala-0.2.0-py3-none-any.whl` has SHA-256 `7b1ed90f928e4cdb4c369f6ceab6f682a4081dfceb233d9e8d72598e6b5a477f`. Its exact v0.20.0 support matrix passed two byte-identical repetitions of all four probes.
- `python -m pytest` passed 682 tests. `ruff check .`, `lefthook validate`, both pack validations, `python -m build`, `python -m twine check dist/*`, and `python scripts/check_release_contents.py . --wheel dist/*.whl` passed; release-content verification found 267 tracked files and 63 wheel members.
- `python scripts/check_records.py .` passed with 3 capabilities, 2 change records, and 1 wireframe; `python scripts/check_md_links.py .` passed across 85 Markdown files.
- A live `hermes send` success receipt was not exercised because the isolated host intentionally had no external gateway credentials and the evaluation must not emit platform messages. Source inspection retained the `success`, `platform`, and `message_id` fields Daidala validates for supported built-in senders; attended delivery remains a post-upgrade check.

The repository now admits exact Hermes v0.20.0. Upgrading the active production Hermes installation and exercising a live external delivery receipt remain separate attended operator actions.
