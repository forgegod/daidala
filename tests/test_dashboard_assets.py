"""Dashboard UI asset and registration tests.

Bounded dashboard operator UI. These tests pin the asset surface that
the Hermes dashboard host discovers and serves through the Phase 0 plugin
extension boundary. They prove:

- the ``manifest.json`` registers exactly the tab, slot, and assets that
  Phase 0 proved against the supported host;
- the IIFE bundle uses the documented SDK registration helpers and only its
  bounded preview-confirm mutation allowlist;
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
        "name": "daidala",
        "label": "Daidala",
        "version": "0.2.0",
        "tab": {"path": "/daidala", "position": "after:kanban"},
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
    assert "PLUGIN_NAME = \"daidala\"" in source
    assert 'register(PLUGIN_NAME, Page)' in source
    assert 'registerSlot(PLUGIN_NAME, "sessions:top", Slot)' in source
    assert "buildDecisionCount" in source


def test_dashboard_mutations_use_only_closed_post_routes() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert "SDK.fetchJSON" in source
    assert 'method: "GET"' in source
    assert 'Accept: "application/json"' in source
    assert "__HERMES_SESSION_TOKEN__" not in source
    assert 'method: "POST"' in source
    assert 'API_BASE + "/wizard/readiness"' in source
    assert 'API_BASE + "/wizard/preview"' in source
    assert 'API_BASE + "/wizard/start"' in source
    assert 'API_BASE + "/wizard/boards/preview"' in source
    assert 'API_BASE + "/wizard/boards"' in source
    assert '"Repository path"' not in source
    assert '"/install/preview"' in source
    assert '"/install"' in source
    assert "preview_digest: previewDigest, confirm: true" in source
    assert '"/approval-review"' in source
    assert '"/approve"' in source
    assert "artifact_id: plan.artifact_id" in source
    assert "plan_digest: plan.plan_digest" in source
    assert "summary_digest: plan.summary_digest" in source
    assert '"I reviewed this exact plan"' in source
    assert '"/cards/" + encodeURIComponent(card.task_id) +' in source
    assert '"/cancel/preview"' in source
    assert '"/cancel"' in source
    assert "method: \"PATCH\"" not in source


def test_bundle_exposes_preview_confirmed_initialization_and_bounded_diagnosis() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required = (
        'API_BASE + "/initialization"',
        'API_BASE + "/diagnostics/prerequisites"',
        "preview_digest: previewDigest",
        "confirm: true",
        "Open initialization preview",
        "← Back to verification",
        "I confirm this exact initialization preview",
        "Run local checks",
        "Run live checks",
        "project_id: projectId",
        "live: live",
    )
    for text in required:
        assert text in source

    assert 'data-testid": "daidala-initialization"' in source
    assert "project_manifest:" not in source
    assert "registration_path:" not in source


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
    assert '"Preview mutations"' not in source
    assert '"Start workflow"' in source
    assert '"Preview constraint change"' in source
    assert '"Apply replacement"' in source
    assert '"No semantic change; replacement is unnecessary."' in source
    assert "expected_current_digest" in source


def test_bundle_exposes_schema_aware_constraint_authoring_and_source_selection() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        'API_BASE + "/constraints/sources"',
        '"/constraints/sources/" + encodeURIComponent(name)',
        "Constraints",
        "Reusable policy sources",
        "Workflow policy maintenance",
        "New workflow constraints",
        "Edit constraints",
        "create with null current digest",
        "Insert schema skeleton",
        "Copy selected template into draft",
        "Use as reference skill",
        "Create constraints",
        "Apply replacement",
        "Use selected source in Start draft",
        "canonical_content",
        "Preview digest ",
        "worker card body 8192 characters",
        "expected_current_digest: currentDigest",
        "constraint_template",
        "schemaLimits",
    )
    for text in required_strings:
        assert text in source, f"missing constraint authoring contract text: {text}"

    assert 'data-testid": "daidala-constraint-authoring"' in source
    assert 'data-testid": "daidala-constraint-source"' in source
    assert "innerHTML" not in source
    assert "constraints/sources/{path}" not in source


def test_bundle_exposes_pack_inventory_readiness_content_and_confirmed_install() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        'API_BASE + "/packs"',
        '"/validate"',
        '"/check"',
        '"/skills/"',
        "Configuration",
        "Packs",
        "Validate",
        "Check readiness",
        "Preview installation",
        "installed SKILL.md",
        "expected ",
        "observed ",
        "Bundled adapter · check only",
        "I confirm these exact external skill installations",
        "Install external skills",
    )
    for text in required_strings:
        assert text in source, f"missing pack UI contract text: {text}"

    assert 'data-testid": "daidala-pack"' in source
    assert 'data-testid": "daidala-skill-content"' in source
    assert 'data-testid": "daidala-pack-preview"' in source
    assert '"/dispatch"' not in source.lower()
    assert "dispatch_tool" not in source.lower()


def test_bundle_exposes_path_free_github_project_link_management() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        'API_BASE + "/registrations"',
        'API_BASE + "/github-project-links"',
        'API_BASE + "/github-project-links/preview"',
        '"/verify"',
        'method: "PUT"',
        'method: "DELETE"',
        "GitHub Projects",
        "Registration context",
        "No GitHub Project configured",
        "Preview link change",
        "Verify",
        "I confirm applying this exact verified link",
        "I confirm removing this GitHub Project link",
        "linkIssueMessage",
        "payload.detail",
        "checkout_match",
        "intake_credential",
        "project_node_id",
    )
    for text in required_strings:
        assert text in source, f"missing GitHub Project link UI contract text: {text}"

    assert 'data-testid": "daidala-github-project-links"' in source
    assert 'data-testid": "daidala-github-project-link"' in source
    assert "checkout_path" not in source
    assert "repository_path" not in source


def test_bundle_exposes_confirmed_path_free_checkout_lifecycle_actions() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        'API_BASE + "/checkouts"',
        '"/" + kind + "/preview"',
        '"/" + pending.kind',
        '"/checkouts/_backups/prune/preview"',
        '"/checkouts/_backups/prune"',
        '"/checkouts/policy/preview"',
        '"/checkouts/policy"',
        "Checkouts",
        "Preview refresh",
        "Preview adoption",
        "Preview prune",
        "Preview policy change",
        "I confirm applying this exact checkout preview",
        "Apply confirmed checkout action",
    )
    for text in required_strings:
        assert text in source, f"missing checkout UI contract text: {text}"

    assert 'data-testid": "daidala-checkouts"' in source
    assert 'data-testid": "daidala-checkout-preview"' in source
    assert "checkout_path" not in source
    assert "repository_path" not in source


def test_bundle_exposes_read_only_configuration_verification() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        'API_BASE + "/configuration"',
        "Verification",
        "Configuration verification",
        "Refresh verification",
        "Read-only persisted configuration",
        "Checkout policy",
        "Derived checkout: ",
        "GitHub intake: ",
        "Evaluator: ",
        "Notifications: ",
        "node_id_configured",
        "Manual stale refresh may wipe or back up clean local data",
    )
    for text in required_strings:
        assert text in source, f"missing configuration verification contract text: {text}"

    panel = source[
        source.index("function ConfigurationVerificationPanel"):
        source.index("function ConstraintAuthoringPanel")
    ]
    assert 'data-testid": "daidala-configuration-verification"' in panel
    assert "project_node_id" not in panel
    assert ".daidala-banner-warning" in (DASHBOARD / "dist" / "style.css").read_text(
        encoding="utf-8"
    )


def test_bundle_exposes_the_closed_inventory_backed_start_workflow_wizard() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        'API_BASE + "/wizard/inventory"',
        'API_BASE + "/wizard/readiness"',
        'API_BASE + "/wizard/preview"',
        'API_BASE + "/wizard/start"',
        'API_BASE + "/wizard/boards/preview"',
        'API_BASE + "/wizard/boards"',
        "Mounted controller profile",
        "Registered repository",
        "Requested outcome / Prompt",
        "Worker profile default",
        "Advanced workflow settings",
        "Workflow constraints",
        "Write YAML",
        "Reference skill",
        "No constraints",
        "Installed policy source",
        "Manage sources",
        "Manage packs",
        "Workflow identity (optional)",
        "Save as default",
        "Create board",
        "New board display name",
        "Start readiness",
        "I confirm applying this exact preview",
        "Start now",
        "Open Hermes Cron",
        "daidala:start-default:v1:",
    )
    for text in required_strings:
        assert text in source, f"missing Start workflow contract text: {text}"

    assert 'data-testid": "daidala-start-workflow"' in source
    assert 'data-testid": "daidala-start-readiness"' in source
    assert "localStorage" in source
    assert '"target_repository"' not in source
    assert "inventory.policy_sources" in source
    assert 'profiles.indexOf("default")' in source
    assert 'href: "/cron"' in source
    assert 'href: "#cron"' not in source
    assert 'href: "#config-constraints"' not in source
    assert "/daidala?section=constraints&return=start-workflow" in source
    assert "window.history.pushState" in source
    assert 'addEventListener("popstate"' in source
    assert "Hermes Cron schedules future admissions only" in source
    assert "existingWorkflowId" in source
    assert "Opened it without creating a second workflow" in source


def test_bundle_reopens_a_started_workflow_without_an_incomplete_duplicate() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert "var summary = detail && detail.workflow ? detail.workflow : workflow;" in source
    assert "row.workflow_id !== openWorkflowId" in source
    assert "listedWorkflows.map" in source


def test_bundle_renders_every_phase_three_state() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        "Loading workflows",
        "No Daidala workflows",
        "Live Kanban state unavailable",
        "No pending human decision",
        "Daidala decisions:",
        "Refresh",
        "Loading card status",
        "Loading decisions",
        "Live Kanban and audit detail",
        "Needs your decision",
        "Human approval — Daidala policy gate",
        "Human review disposition — Daidala policy gate",
        "What the next card receives",
        "Plan unavailable",
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


def test_exact_plan_body_is_rendered_as_literal_text() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert 'createElement("pre", { className: "daidala-plan-text" }, plan.content)' in source
    assert "innerHTML" not in source
    assert "dangerouslySetInnerHTML" not in source


def test_revision_navigation_reopens_only_matching_exact_plan_approval() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert "function dashboardRoute()" in source
    assert 'decision: decision === "plan-approval" ? decision : null' in source
    assert "planRevision: planRevision && /^\\d+$/.test(planRevision)" in source
    assert 'window.dispatchEvent(new PopStateEvent("popstate"));' in source
    assert 'setOpenWorkflowId(nextRoute.workflowId);' in source
    assert 'key: openWorkflowId' in source
    assert 'revision !== props.planRevision' in source
    assert 'document.querySelector(\'[data-testid="daidala-approval-packet"]\')' in source
    assert 'panel.scrollIntoView({ block: "start" });' in source


def test_review_evidence_and_disposition_use_only_named_literal_routes() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        '"/review-decision"',
        '"/review-disposition/preview"',
        '"/review-disposition"',
        "Human review disposition",
        "Read exact captured diff",
        "Changed paths",
        "Verification evidence",
        "Reviewer outcome",
        "Fixed consequences",
        "Accept and continue to delivery",
        "Required revision feedback",
        "What the successor Plan card receives",
        "I confirm applying this exact review disposition",
        "Opening successor exact-plan approval",
        "Challenge reviewer uses public Kanban comment and unblock controls",
    )
    for text in required_strings:
        assert text in source, f"missing review disposition contract text: {text}"

    literal_diff = (
        'createElement("pre", { className: "daidala-review-diff" }, '
        "implementation.content)"
    )
    assert literal_diff in source
    assert "var actions = packet && Array.isArray(packet.allowed_actions)" in source
    assert "actor:" not in source
    assert "worktree_to_release" not in source
    assert "innerHTML" not in source
    assert "dangerouslySetInnerHTML" not in source


def test_blocked_card_remediation_and_cancellation_use_preview_confirm_routes() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        "Blocked card",
        "Stage: ",
        "Blocker kind",
        "Requested remediation",
        "Latest relevant evidence",
        "Comment remediation",
        "Unblock for retry",
        "Preview cancellation",
        "Affected cards",
        "Daidala-owned worktree",
        "I confirm cancelling this workflow",
        "Cancellation reason",
    )
    for text in required_strings:
        assert text in source, f"missing recovery/cancellation UI text: {text}"

    assert "worktree_path" not in source
    assert '"/dispatch"' not in source.lower()
    assert "card.block_kind" in source
    assert "recommendation.rationale" in source


def test_bundle_targets_phase_two_read_endpoints() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert 'API_BASE = "/api/plugins/daidala"' in source
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
    assert "daidala-state-unavailable" in source or "daidala-workflow-unavailable" in source


def test_stylesheet_uses_host_theme_tokens() -> None:
    source = (DASHBOARD / "dist" / "style.css").read_text(encoding="utf-8")

    assert "var(--text-primary" in source
    assert "var(--surface-raised" in source
    assert "var(--accent-primary" in source or "var(--daidala-accent" in source


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