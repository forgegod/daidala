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
    assert '"/wizard/boards"' in source
    assert '"Repository path"' not in source
    assert "delivery_credential_alias" not in source
    assert '"/skills/action/preview"' in source
    assert '"/skills/action"' in source
    assert "preview_digest: preview.preview_digest" in source
    assert "confirm: true" in source
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


def test_bundle_exposes_catalog_first_pack_inventory_and_confirmed_pack_actions() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")
    styles = (DASHBOARD / "dist" / "style.css").read_text(encoding="utf-8")

    required_strings = (
        'API_BASE + "/packs"',
        '"/check"',
        '"/install/preview"',
        '"/install/stream"',
        '"/skills/"',
        "Configuration",
        "Workflow packs",
        "Install a complete immutable catalog once",
        "Catalog-only",
        "Stage bindings select activation; the catalog owns installation.",
        "Skill inventory",
        "Install workflow pack?",
        "Confirm shared installation",
        "shared Hermes skill store",
        "Profile effect",
        "Successful installs remain",
        "retry offers only missing targets",
        "View failure receipt",
        "Installing skill ",
        '"aria-live": "polite"',
        "installProgress.skill",
        "installProgress.position",
        "installProgress.total",
        "Confirm profile-local change",
        "Installation and every other Hermes profile remain unchanged.",
        "Install this skill through the pack-wide action.",
        "Open immutable source",
        "source_url",
        "enabled",
        "Ready with warnings",
        "Digest mismatch warning. The installed skill remains available.",
        "Search skills or lifecycle stage",
        "Show all ",
        "trapDialogFocus",
        "returnFocus",
        '"/skills/action/preview"',
        '"/skills/action"',
    )
    for text in required_strings:
        assert text in source, f"missing pack UI contract text: {text}"

    assert 'data-testid": "daidala-pack"' in source
    assert 'data-testid": "daidala-skill-content"' in source
    assert 'data-testid": "daidala-pack-preview"' in source
    assert 'data-testid": "daidala-pack-install-preview"' in source
    assert 'data-testid": "daidala-pack-install-progress"' in source
    assert "SDK.authedFetch" in source
    assert "TextDecoder" in source
    assert 'role: "dialog"' in source
    assert '"aria-modal": "true"' in source
    assert 'event.key === "Escape"' in source
    assert 'event.key !== "Tab"' in source
    assert "event.currentTarget.querySelector('[role=\"dialog\"]')" in source
    assert '"[tabindex=\\"-1\\"], button:not([disabled])' in source
    assert "documentView && !actionPreview" in source
    assert "actionReturnsToDetailRef" in source
    assert "var visibleSkillCount =" in source
    assert 'visibleSkillCount + " of " + filteredSkills.length + " shown"' in source
    assert 'className: "sr-only"' not in source
    assert 'createElement("span", null, "Search skills")' in source
    assert 'className: "daidala-skill-name"' in source
    assert source.count("loadContent(event, skill.name)") == 1
    assert "documentView.activation.join" in source
    assert "documentView.activations" not in source
    assert 'runActionPreview("install"' not in source
    assert 'documentAction = "install"' not in source
    assert "Install skill above" not in source
    assert ".daidala-pack-workspace" in styles
    assert ".daidala-pack-disclosure" in styles
    assert "@media (max-width: 48rem)" in styles
    assert "pinned source SKILL.md" not in source
    assert '"pinned-source"' not in source
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
        "project_node_id",
    )
    for text in required_strings:
        assert text in source, f"missing GitHub Project link UI contract text: {text}"

    assert 'data-testid": "daidala-github-project-links"' in source
    assert 'data-testid": "daidala-github-project-link"' in source
    assert "checkout_path" not in source
    assert "repository_path" not in source
    assert "intake_credential" not in source


def test_bundle_exposes_confirmed_path_free_repository_registration() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        'API_BASE + "/repository-registration/preview"',
        'API_BASE + "/repository-registration"',
        'API_BASE + "/repository-registration/inventory"',
        "GitHub Repositories",
        "Every existing Hermes profile and its registered workspace tuples",
        "Repository",
        "Slug",
        "Board",
        "GitHub Project",
        "github.com/",
        "No repository registered",
        "Register another repository",
        "GitHub repository link",
        "Inspect repository",
        "Registration preview",
        "Manifest digest:",
        "Release policy:",
        "credential ",
        "This action does not commit, push, create a GitHub Project, or store a token.",
        "I confirm registering this exact repository",
        "Register repository",
        "needs-bootstrap",
        "Bootstrap Daidala policy on a non-default branch",
        "Bootstrap preview",
        "Bootstrap repository policy",
        'API_BASE + "/repository-registration/bootstrap/preview"',
        'API_BASE + "/repository-registration/bootstrap"',
        "Open bootstrap branch",
        "Open .daidala on bootstrap branch",
        "Open a pull request",
    )
    for text in required_strings:
        assert text in source, f"missing repository registration UI contract text: {text}"

    configuration_panel = source[
        source.index("function ConfigurationPanel") : source.index("function configurationStatus")
    ]
    assert '}, "GitHub Repositories"),' in configuration_panel
    assert '}, "GitHub Projects"),' in configuration_panel
    assert 'data-testid": "daidala-repository-registration"' in source
    assert 'data-testid": "daidala-repository-profile"' in source
    assert "Selected Hermes profile" not in source
    assert "checkout_path" not in source
    assert "repository_path" not in source
    assert "token:" not in source.lower()
    assert "delivery_credential_alias" not in source
    assert (
        'window.open(bootstrapPreview.links.compare_pull_request, "_blank", '
        '"noopener,noreferrer")' in source
    )
    assert "Open compare / create pull request on GitHub" not in source
    assert '(pr ? " " + pr : "")' not in source


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


def test_bundle_exposes_operator_runbook_without_host_lifecycle_mutations() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required = (
        'data-testid": "daidala-operator-runbook"',
        '"Runbook"',
        "Install and enable",
        "Initialize",
        "Diagnose prerequisites",
        "Start and resume",
        "Approve the exact plan",
        "Review disposition",
        "Cancel and recovery",
        "Upgrade",
        "Standalone diagnostics",
        "Host-owned CLI",
        "Resume existing workflow ID",
        "Opened the existing workflow and resumed read-only polling.",
        "supported_hermes_range",
    )
    for text in required:
        assert text in source

    assert 'API_BASE + "/plugins"' not in source
    assert 'API_BASE + "/gateway"' not in source
    runbook = source[
        source.index("function OperatorRunbookPanel"):
        source.index("function ConfigurationVerificationPanel")
    ]
    assert "props.onResume" in runbook
    assert "runStart" not in runbook

def test_bundle_exposes_the_closed_inventory_backed_start_workflow_wizard() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required_strings = (
        'API_BASE + "/wizard/inventory"',
        'API_BASE + "/wizard/readiness"',
        'API_BASE + "/wizard/preview"',
        'API_BASE + "/wizard/start"',
        'API_BASE + "/wizard/local/preview"',
        'API_BASE + "/wizard/local/start"',
        "Mounted controller profile",
        "Pack · readiness",
        "Registered GitHub repository",
        "Register repository",
        "Initialize local project",
        "Project slug",
        "Board display name",
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
    assert "inventory.pack_options" in source
    assert 'status: "readiness unavailable"' in source
    assert '"installation required"' in source
    assert "result && result.ready" in source
    assert "actions.length" in source
    assert "requires external skill installation before a workflow can start" in source
    assert "ready_packs" not in source
    assert "localStorage" in source
    assert '"target_repository"' not in source
    assert "inventory.policy_sources" in source
    assert 'profiles.indexOf("default")' in source
    assert 'href: "/cron"' in source
    assert 'href: "#cron"' not in source
    assert 'href: "#config-constraints"' not in source
    assert "/daidala?section=constraints&return=start-workflow" in source
    assert "/daidala?section=repositories&return=start-workflow" in source
    assert "controller_profile: form.controller_profile" in source
    assert "Existing unregistered repository" in source
    assert "No GitHub repository is registered in this Hermes installation" in source
    assert "inventory.ineligible_repositories" in source
    assert "Not selectable" in source
    assert "Reason: " in source
    assert "Conclusion: " in source
    assert "Working directory: " in source
    assert 'data-testid": "daidala-ineligible-repositories"' in source
    assert "window.history.pushState" in source
    assert 'addEventListener("popstate"' in source
    assert "Hermes Cron schedules future admissions only" in source
    assert "existingWorkflowId" in source
    assert "Opened it without creating a second workflow" in source


def test_start_workflow_disables_primary_navigation_that_cannot_preserve_the_draft() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    assert 'disabled: starting && view.value !== "workflows"' in source
    assert 'title: starting && view.value !== "workflows"' in source
    assert "Finish or close Start workflow before changing views." in source
    assert ".daidala-primary-nav button:disabled" in (
        DASHBOARD / "dist" / "style.css"
    ).read_text(encoding="utf-8")


def test_routed_start_configuration_is_scrolled_and_focused_after_render() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")
    config_panel = source[
        source.index("function ConfigurationPanel") : source.index("function configurationStatus")
    ]

    assert "var panelRef = useRef(null);" in config_panel
    assert "ref: panelRef" in config_panel
    assert "tabIndex: -1" in config_panel
    assert '"aria-label": "Configuration"' in config_panel
    assert "if (!props.section || !panelRef.current) return;" in config_panel
    assert 'panelRef.current.focus({ preventScroll: true });' in config_panel
    assert 'panelRef.current.scrollIntoView({ block: "start" });' in config_panel


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


def test_branch_delivery_uses_only_preview_confirmed_path_free_routes() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")

    required = (
        "function WorkflowDelivery(props)",
        '"/delivery/preview"',
        '"/delivery"',
        "Preview branch delivery",
        "Confirm commit and push branch",
        "I confirm committing and pushing this exact branch delivery",
        "Delivery credential unavailable.",
        "Branch delivery completed:",
        'data-testid": "daidala-delivery"',
    )
    for text in required:
        assert text in source, f"missing branch delivery contract text: {text}"

    panel = source[
        source.index("function WorkflowDelivery") : source.index("function renderTimeline")
    ]
    assert "credential_alias" not in panel
    assert "token" not in panel.lower()
    assert "worktree_path" not in panel
    assert "innerHTML" not in panel
    assert "dangerouslySetInnerHTML" not in panel


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


def test_bundle_exposes_authenticated_artifact_review_and_curator_controls() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")
    style = (DASHBOARD / "dist" / "style.css").read_text(encoding="utf-8")

    required = (
        'API_BASE + "/artifacts"',
        '"/text"',
        '"/download"',
        'API_BASE + "/artifact-curator"',
        'SDK.authedFetch',
        '"Workflows"',
        '"Artifacts"',
        '"Config"',
        'data-testid": "daidala-artifacts"',
        'data-testid": "daidala-artifact-literal-preview"',
        'data-testid": "daidala-curator-preview"',
        '"Literal text preview"',
        '"Download verified bytes"',
        '"Preview pin"',
        '"Preview unpin"',
        '"Preview archive"',
        '"Preview restore"',
        "I confirm applying this exact curator preview",
        "preview_digest: preview.preview_digest",
        "confirm: true",
    )
    for text in required:
        assert text in source, f"missing artifact-review contract text: {text}"

    panel = source[source.index("function ArtifactsPanel"):source.index("function Page()")]
    assert 'createElement("pre", null, text.content)' in panel
    assert "innerHTML" not in panel
    assert "dangerouslySetInnerHTML" not in panel
    assert "path:" not in panel
    assert ".daidala-primary-nav" in style
    assert ".daidala-artifact-layout" in style
    assert ".daidala-artifact-preview pre" in style


def test_bundle_explains_primary_screens_and_keeps_model_advice_on_demand() -> None:
    source = (DASHBOARD / "dist" / "index.js").read_text(encoding="utf-8")
    style = (DASHBOARD / "dist" / "style.css").read_text(encoding="utf-8")

    required = (
        "Workflow supervision",
        "Artifact evidence",
        "Configuration readiness",
        "No workflow is recorded for this profile.",
        "If the catalog is empty, no workflow has captured evidence yet.",
        "Readiness advice",
        "Analyze Daidala readiness",
        'API_BASE + "/setup-analysis"',
        "Model advice unavailable. Deterministic guidance remains available.",
        "does not replace deterministic workflow recommendations",
        'data-testid": "daidala-setup-advice"',
        'data-testid": "daidala-screen-guidance-"',
        "Config → Packs",
        "Config → GitHub Projects",
        "Config → Checkouts",
        "Config → Constraints",
        "Config → Verification",
        "Config → Runbook",
    )
    for text in required:
        assert text in source, f"missing dashboard guidance: {text}"

    advice_panel = source[
        source.index("function SetupAdvicePanel"):source.index("function ConfigurationPanel")
    ]
    assert "useEffect" not in advice_panel
    assert "requestSetupAnalysis()" in advice_panel
    assert "openDashboardTarget(priority.target)" in advice_panel
    assert "priority.screen" not in advice_panel
    assert (
        '"Open " + (ADVICE_TARGETS[priority.target] || { label: "Dashboard" }).label'
        in advice_panel
    )
    assert (
        '"config-packs": { label: "Config → Packs", '
        'path: "/daidala?view=config&section=packs" }'
    ) in source
    assert ".daidala-screen-guidance" in style
    assert ".daidala-setup-advice" in style


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