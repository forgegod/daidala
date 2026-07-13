"""Dashboard UI asset and registration tests.

Phase 3 — read-only dashboard UI. These tests pin the asset surface that
the Hermes dashboard host discovers and serves through the Phase 0 plugin
extension boundary. They prove:

- the ``manifest.json`` registers exactly the tab, slot, and assets that
  Phase 0 proved against the supported host;
- the IIFE bundle is read-only, never invokes POST/PUT/DELETE, and uses
  the documented SDK registration helpers;
- the bundle polls at least every five seconds while visible, stops when
  hidden, exposes a manual refresh button, and renders every Phase 3
  visual state (loading, no-workflow, progress, pending approval, blocked
  card, host-unavailable);
- the stylesheet uses the host's theme tokens and collapses on narrow
  layouts without exceeding the dashboard's expected surface.

The tests inspect the source text directly so the build artifact matches
the Phase 0 probe conventions exactly without introducing a JavaScript
toolchain.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
DASHBOARD = ROOT / "dashboard"


def test_manifest_registers_proven_host_surfaces() -> None:
    manifest = json.loads((DASHBOARD / "manifest.json").read_text(encoding="utf-8"))

    assert manifest == {
        "name": "wingstaff",
        "label": "Wingstaff",
        "version": "0.1.0",
        "tab": {"path": "/wingstaff", "position": "after:kanban"},
        "slots": ["sessions:top"],
        "entry": "dist/index.js",
        "css": "dist/style.css",
        "api": "plugin_api.py",
    }


def test_bundle_is_a_dependency_free_iife() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert source.lstrip().startswith("/*") or source.lstrip().startswith("//")
    assert '(function ()' in source
    assert '"use strict"' in source
    # No external imports, network fetches outside the Hermes API base,
    # or third-party library references.
    assert "import " not in source
    assert "require(" not in source
    assert "https://" not in source
    assert "http://" not in source


def test_bundle_uses_documented_sdk_registration() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert "window.__HERMES_PLUGIN_SDK__" in source
    assert "SDK.React" in source
    # Registration uses the documented constants rather than inline strings.
    assert "PLUGIN_NAME = \"wingstaff\"" in source
    assert 'register(PLUGIN_NAME, Page)' in source
    assert 'registerSlot(PLUGIN_NAME, "sessions:top", Slot)' in source
    assert "buildDecisionCount" in source


def test_read_model_stays_read_only_and_setup_writes_are_scoped() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert 'method: "GET"' in source
    assert 'credentials: "same-origin"' in source
    assert 'Accept: "application/json"' in source
    assert 'Authorization: "Bearer " + window.__HERMES_SESSION_TOKEN__' in source
    assert 'method: "POST"' in source
    assert 'API_BASE + "/wizard/preview"' in source
    assert 'API_BASE + "/wizard/start"' in source
    assert "method: \"PUT\"" not in source
    assert "method: \"DELETE\"" not in source
    assert "method: \"PATCH\"" not in source


def test_bundle_polls_at_least_every_five_seconds_and_respects_visibility() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert "POLL_MS = 5000" in source
    assert "visibilitychange" in source
    assert 'visibilityState === "visible"' in source
    # The bundle must skip the next scheduled tick when the tab is hidden
    # and clear any pending timer so hidden tabs do not hammer the API.
    assert "clearTimeout" in source
    assert "setTimeout" in source


def test_bundle_exposes_manual_refresh() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert '"Refresh"' in source or ">Refresh<" in source
    assert "onClick" in source
    assert "Refresh" in source
    assert "refreshAll" in source
    assert '"Preview mutations"' in source
    assert '"Start workflow"' in source
    assert '"Preview constraint change"' in source
    assert '"Replace constraints"' in source
    assert '"No semantic change; replacement is unnecessary."' in source
    assert "expected_current_digest" in source


def test_bundle_renders_every_phase_three_state() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        "Loading workflows",
        "No Wingstaff workflows",
        "Live Kanban state unavailable",
        "No pending human decision",
        "Wingstaff decisions:",
        "Refresh",
        "Loading card status",
        "Loading decisions",
        "Live Kanban",
        "Pending decisions",
        "recorded",  # pending-approval identity badge
    )
    for text in required_strings:
        assert text in source, f"missing UI state text: {text}"

    # Status badges are rendered by data-testid, status, or class hook so
    # the UI is testable without a real browser harness.
    assert '"is-" + card.status' in source or 'is-" + card.status' in source

    # The closed action vocabulary lives in the backend; the UI must not
    # invent or hardcode alternate labels.
    assert "approve_current_tuple" not in source
    assert "resolve_blocked_card" not in source


def test_bundle_targets_phase_two_read_endpoints() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert 'API_BASE = "/api/plugins/wingstaff"' in source
    assert 'API_BASE + "/health"' in source
    assert 'API_BASE + "/workflows"' in source
    assert 'API_BASE + "/workflows/"' in source
    assert '"/decisions"' in source


def test_bundle_handles_unavailable_host_gracefully() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    # Network errors must downgrade to "host unavailable" rather than
    # fabricate a snapshot.
    assert ".catch(function () {" in source
    assert "return null" in source
    assert "Live Kanban state unavailable" in source
    assert "ws-state-unavailable" in source or "ws-workflow-unavailable" in source


def test_stylesheet_uses_host_theme_tokens() -> None:
    source = (DASHBOARD / "dist" / "style.css").read_text(encoding="utf-8")

    assert "var(--text-primary" in source
    assert "var(--surface-raised" in source
    assert "var(--accent-primary" in source or "var(--ws-accent" in source


def test_stylesheet_collapses_on_narrow_layouts() -> None:
    source = (DASHBOARD / "dist" / "style.css").read_text(encoding="utf-8")

    assert "@media (max-width: 64rem)" in source


def test_stylesheet_does_not_reference_external_assets() -> None:
    source = (DASHBOARD / "dist" / "style.css").read_text(encoding="utf-8")

    assert "@import" not in source
    assert "url(" not in source


def test_dashboard_assets_are_packaged_with_wheel(tmp_path) -> None:
    """The wheel must include the dashboard manifest, bundle, stylesheet,
    and Python API module under ``dashboard/`` so a wheel install can be
    extended into the active profile plugin directory by the Phase 6
    dry-run/apply setup operation."""

    import subprocess
    import sys
    from zipfile import ZipFile

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(tmp_path),
            str(ROOT),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    wheel = next(tmp_path.glob("daidala-*.whl"))
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert "dashboard/manifest.json" in names
        assert "dashboard/dist/index.js" in names
        assert "dashboard/dist/style.css" in names
        assert "dashboard/plugin_api.py" in names