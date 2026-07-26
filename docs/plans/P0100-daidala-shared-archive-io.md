# Daidala shared archive I/O foundation

**Plan ID:** daidala-shared-archive-io

**Execution slot:** P0100

**Created:** 2026-07-24

**Depends on:** none

**Split from:** daidala-artifact-review-access-and-curation

**Entry checkpoint:** none — this is the first dependency-ready unit

**Context sources:** `AGENTS.md`, `daidala/AGENTS.md`, `tests/AGENTS.md`, `docs/15-self-improvement.md:211-227`, and `docs/16-self-improvement-setup.md:123-145`

**Produces:** policy-neutral verified archive creation, manifest validation, and safe extraction in `daidala/archive_io.py`

**Status:** pending — design captured; human approval is required before Phase 0 implementation starts.

Daidala will provide one policy-neutral, verified tar/gzip implementation for workflow artifact archives and dashboard checkout backups, without moving either feature's eligibility, retention, storage-root, or authorization policy into the shared helper.

## Current state

- Workflow evidence currently lives below `<profile-data-root>/daidala/workflows/<workflow-id>/artifacts/`; historical paths and digests are immutable evidence (`docs/15-self-improvement.md:211-227`, `docs/16-self-improvement-setup.md:123-145`).
- The dashboard checkout plan requires safe tar/gzip creation under `<checkouts.root>/_backups/`, but `daidala/checkouts.py` and a shared archive helper do not exist yet ([P0220](P0220-daidala-dashboard-checkouts-and-project-links.md)).
- The follow-on artifact curation plan requires verified, restorable workflow archives under the profile-local Daidala data root ([P0310](P0310-daidala-artifact-curation.md)).
- Runtime data resolves through the active Hermes home/profile; no implementation may hard-code `~/.hermes` (`daidala/locations.py:33-52`).

## Risk call-out

Archive inputs may contain credentials, private paths, or other sensitive content. The helper must never log member names or bytes on failure. Archive directories use mode `0700`; archives, manifests, and restored files use mode `0600`. A failed or interrupted operation must not publish an unverified archive or remove source bytes.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add shared archive I/O | pending | `pytest tests/test_archive_io.py tests/test_execution.py -q` and `python scripts/check_md_links.py .` exit 0; both dependent plans name the shared helper instead of a second tar implementation |

Mark a phase `in-progress` while running it, `done (<sha-or-evidence>)` once its gate passes, and `pending` otherwise.

## Phase 0 — Add shared archive I/O

**Goal:** Define one safe archive implementation contract that Daidala artifact curation and the pending checkout-backup feature can share without sharing policy or storage locations.

**Steps:**

1. Re-read `/AGENTS.md`, `daidala/AGENTS.md`, `dashboard/AGENTS.md`, `tests/AGENTS.md`, and this plan before edits. Re-run `git status --short --branch`; stop if unrelated working-tree changes overlap the target files.
2. Add `daidala/archive_io.py` as a policy-neutral helper for creating, verifying, inventorying, and restoring tar/gzip archives. It accepts an already-authorized source root and explicit relative members; it owns no artifact identity, workflow, checkout, retention, or HTTP decisions.
3. Pin the shared archive contract:
   - archive members are relative POSIX paths beneath the authorized root;
   - reject absolute paths, `..`, duplicate members, symlinks, hard links, sockets, devices, FIFOs, and path escapes;
   - direct regular-file enumeration only, with explicit file-count, per-file, total-uncompressed, and archive-size bounds;
   - write a temporary archive and strict JSON manifest, `fsync`, verify every member size and SHA-256 by reopening the archive, then publish with `os.replace`;
   - archive directory mode is `0700`; archive and manifest modes are `0600`;
   - errors identify the operation and classified cause without returning filenames or bytes that may be sensitive;
   - retries accept only byte/digest-equivalent published output and reject conflicting content.
4. Add `tests/test_archive_io.py` covering round trips, binary bytes, deterministic manifests, mode checks, partial-write cleanup, ENOSPC/EACCES simulation, member/size overflow, path traversal, symlink and special-file rejection, digest mismatch, conflicting retries, and idempotent restore.
5. Confirm the dashboard plan consumes `archive_io.py` for checkout backups and the artifact review plan consumes it for workflow archives. Checkout backups remain under `<checkouts.root>/_backups/`; workflow artifact archives remain under the profile-local Daidala data root.

**Verification gate:** `pytest tests/test_archive_io.py tests/test_execution.py -q` and `python scripts/check_md_links.py .` exit 0; the dependent plans resolve this plan by `Plan ID`; no second tar implementation is specified.

## Out of scope

- Checkout eligibility, refresh, replacement, pruning, or storage-root policy.
- Workflow artifact catalog, access, curation eligibility, retention, scheduling, or dashboard controls.
- Automatic deletion of checkout backups or workflow archives.
- Any Daidala daemon, HTTP server, nested `hermes chat`, or private Hermes module integration.
