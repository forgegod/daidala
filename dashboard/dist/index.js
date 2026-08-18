/*
 * Daidala dashboard UI — bounded operator surface.
 *
 * The plugin renders two components through the Hermes dashboard plugin SDK:
 *
 *   - the /daidala tab (Page) provides Workflows, Artifacts, and Config views;
 *   - the sessions:top slot (Slot) renders a compact pending-decision count.
 *
 * Live state is polled on a fixed >= 5 second cadence while the page is visible;
 * the timer is paused when the tab is hidden. Mutations are limited to the named
 * pack, board, setup, constraint, GitHub Project link, exact-plan, review, and
 * artifact-curator preview-confirm routes. Host-model setup advice is an
 * explicit, read-only POST request and never runs during polling.
 *
 * The Hermes dashboard host invokes this bundle once per session after
 * authenticating and discovering the manifest. The SDK exposes React and
 * registration helpers through window.__HERMES_PLUGIN_SDK__ and
 * window.__HERMES_PLUGINS__ respectively.
 */

(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !SDK.React || !window.__HERMES_PLUGINS__) {
    return;
  }

  var React = SDK.React;
  var createElement = React.createElement;
  var useEffect = React.useEffect;
  var useMemo = React.useMemo;
  var useRef = React.useRef;
  var useState = React.useState;

  var POLL_MS = 5000;
  var API_BASE = "/api/plugins/daidala";
  var PLUGIN_NAME = "daidala";
  var ADVICE_TARGETS = {
    workflows: { label: "Workflows", path: "/daidala?view=workflows" },
    artifacts: { label: "Artifacts", path: "/daidala?view=artifacts" },
    "config-packs": { label: "Config → Packs", path: "/daidala?view=config&section=packs" },
    "config-github-projects": { label: "Config → GitHub Projects", path: "/daidala?view=config&section=github-projects" },
    "config-checkouts": { label: "Config → Checkouts", path: "/daidala?view=config&section=checkouts" },
    "config-constraints": { label: "Config → Constraints", path: "/daidala?view=config&section=constraints" },
    "config-verification": { label: "Config → Verification", path: "/daidala?view=config&section=verification" },
    "config-runbook": { label: "Config → Runbook", path: "/daidala?view=config&section=runbook" }
  };

  function fetchJson(url) {
    return SDK.fetchJSON(url, {
      method: "GET",
      headers: {
        Accept: "application/json"
      }
    });
  }

  function postJson(url, payload) {
    return SDK.fetchJSON(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  }

  function putJson(url, payload) {
    return SDK.fetchJSON(url, {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  }

  function deleteJson(url, payload) {
    return SDK.fetchJSON(url, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  }

  function errorText(reason) {
    return reason && typeof reason.message === "string" ? reason.message : "request failed";
  }

  function existingWorkflowId(reason) {
    var message = errorText(reason);
    if (message.indexOf("409:") !== 0) return null;
    try {
      var payload = JSON.parse(message.slice(message.indexOf("{")));
      return payload && payload.detail && payload.detail.code === "workflow_exists"
        ? payload.detail.workflow_id
        : null;
    } catch (_error) {
      return null;
    }
  }

  function navigateDashboard(event, path) {
    event.preventDefault();
    window.history.pushState({}, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function openDashboardTarget(target) {
    var destination = ADVICE_TARGETS[target];
    if (!destination) return;
    window.history.pushState({}, "", destination.path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function dashboardRoute() {
    var query = new URLSearchParams(window.location.search);
    var workflowId = query.get("workflow");
    var decision = query.get("decision");
    var planRevision = query.get("plan_revision");
    var section = query.get("section");
    var requestedView = query.get("view");
    return {
      workflowId: workflowId && workflowId.length <= 512 && workflowId.indexOf("\0") === -1
        ? workflowId
        : null,
      decision: decision === "plan-approval" ? decision : null,
      planRevision: planRevision && /^\d+$/.test(planRevision) ? planRevision : null,
      section: ["packs", "repositories", "github-projects", "checkouts", "constraints", "verification", "runbook"].indexOf(section) >= 0
        ? section
        : null,
      view: section ? "config" : ["workflows", "artifacts", "config"].indexOf(requestedView) >= 0
        ? requestedView
        : "workflows",
      returnToStart: query.get("return") === "start-workflow"
    };
  }

  function buildHealth() {
    return fetchJson(API_BASE + "/health").catch(function () {
      return { success: false };
    });
  }

  function buildPacks() {
    return fetchJson(API_BASE + "/packs").then(function (payload) {
      return {
        profile: payload && typeof payload.profile === "string" ? payload.profile : "unavailable",
        packs: payload && Array.isArray(payload.packs) ? payload.packs : []
      };
    });
  }

  function buildRegistrations() {
    return fetchJson(API_BASE + "/registrations").then(function (payload) {
      return payload && Array.isArray(payload.registrations) ? payload.registrations : [];
    });
  }

  function buildRepositoryRegistrationInventory() {
    return fetchJson(API_BASE + "/repository-registration/inventory").then(function (payload) {
      return payload && Array.isArray(payload.profiles) ? payload.profiles : [];
    });
  }

  function previewRepositoryRegistration(githubUrl, controllerProfile, board) {
    return postJson(API_BASE + "/repository-registration/preview", {
      github_url: githubUrl,
      controller_profile: controllerProfile,
      board: board || null
    });
  }

  function previewRepositoryBootstrap(githubUrl, controllerProfile) {
    return postJson(API_BASE + "/repository-registration/bootstrap/preview", {
      github_url: githubUrl,
      controller_profile: controllerProfile
    });
  }

  function applyRepositoryBootstrap(githubUrl, controllerProfile, previewDigest) {
    return postJson(API_BASE + "/repository-registration/bootstrap", {
      github_url: githubUrl,
      controller_profile: controllerProfile,
      preview_digest: previewDigest,
      confirm: true
    });
  }

  function applyRepositoryRegistration(githubUrl, controllerProfile, previewDigest, board) {
    return postJson(API_BASE + "/repository-registration", {
      github_url: githubUrl,
      controller_profile: controllerProfile,
      preview_digest: previewDigest,
      confirm: true,
      board: board || null
    });
  }

  function previewRegistrationDefaults(controllerProfile, options) {
    var payload = { controller_profile: controllerProfile };
    if (options && options.seed) payload.seed = true;
    if (options && options.defaults) payload.defaults = options.defaults;
    return postJson(API_BASE + "/repository-registration/defaults/preview", payload);
  }

  function applyRegistrationDefaults(controllerProfile, previewDigest, options) {
    var payload = {
      controller_profile: controllerProfile,
      preview_digest: previewDigest,
      confirm: true
    };
    if (options && options.seed) payload.seed = true;
    if (options && options.defaults) payload.defaults = options.defaults;
    return postJson(API_BASE + "/repository-registration/defaults", payload);
  }

  function buildConfiguration() {
    return fetchJson(API_BASE + "/configuration");
  }

  function requestSetupAnalysis() {
    return postJson(API_BASE + "/setup-analysis", {});
  }

  function buildArtifacts(workflowId) {
    var query = workflowId ? "?workflow_id=" + encodeURIComponent(workflowId) : "";
    return fetchJson(API_BASE + "/artifacts" + query).then(function (payload) {
      return payload && Array.isArray(payload.artifacts) ? payload.artifacts : [];
    });
  }

  function buildArtifactText(workflowId, artifactId) {
    return fetchJson(
      API_BASE + "/artifacts/" + encodeURIComponent(workflowId) + "/" +
      encodeURIComponent(artifactId) + "/text"
    );
  }

  function buildCuratorStatus() {
    return fetchJson(API_BASE + "/artifact-curator");
  }

  function previewCurator(workflowId, operation, archiveId) {
    var payload = { operation: operation };
    if (archiveId) payload.archive_id = archiveId;
    return postJson(
      API_BASE + "/artifact-curator/" + encodeURIComponent(workflowId) + "/preview",
      payload
    );
  }

  function applyCurator(workflowId, preview) {
    var payload = {
      operation: preview.operation,
      preview_digest: preview.preview_digest,
      confirm: true
    };
    if (preview.archive_id) payload.archive_id = preview.archive_id;
    return postJson(
      API_BASE + "/artifact-curator/" + encodeURIComponent(workflowId), payload
    );
  }

  function downloadArtifact(entry) {
    var url = API_BASE + "/artifacts/" + encodeURIComponent(entry.workflow_id) + "/" +
      encodeURIComponent(entry.artifact_id) + "/download";
    return SDK.authedFetch(url, { method: "GET" }).then(function (response) {
      if (!response.ok) throw new Error("download failed with status " + response.status);
      var observedDigest = response.headers.get("X-Daidala-Artifact-SHA256");
      if (observedDigest !== entry.digest) throw new Error("download digest identity changed");
      return response.blob();
    }).then(function (blob) {
      var objectUrl = URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = objectUrl;
      link.download = "artifact-" + entry.artifact_id + ".bin";
      link.click();
      URL.revokeObjectURL(objectUrl);
    });
  }

  function buildInitialization() {
    return fetchJson(API_BASE + "/initialization");
  }

  function applyInitialization(previewDigest) {
    return postJson(API_BASE + "/initialization", {
      preview_digest: previewDigest,
      confirm: true
    });
  }

  function runPrerequisiteDiagnosis(projectId, live) {
    return postJson(API_BASE + "/diagnostics/prerequisites", {
      project_id: projectId,
      live: live
    });
  }

  function buildGitHubProjectLinks() {
    return fetchJson(API_BASE + "/github-project-links").then(function (payload) {
      return payload && Array.isArray(payload.links) ? payload.links : [];
    });
  }

  function previewGitHubProjectLink(payload) {
    return postJson(API_BASE + "/github-project-links/preview", payload);
  }

  function verifyGitHubProjectLink(projectId) {
    return postJson(
      API_BASE + "/github-project-links/" + encodeURIComponent(projectId) + "/verify",
      {}
    );
  }

  function readGitHubProjectLink(projectId) {
    return fetchJson(API_BASE + "/github-project-links/" + encodeURIComponent(projectId));
  }

  function replaceGitHubProjectLink(projectId, payload) {
    return putJson(
      API_BASE + "/github-project-links/" + encodeURIComponent(projectId), payload
    );
  }

  function removeGitHubProjectLink(projectId, payload) {
    return deleteJson(
      API_BASE + "/github-project-links/" + encodeURIComponent(projectId), payload
    );
  }

  function validatePack(packName) {
    return postJson(API_BASE + "/packs/" + encodeURIComponent(packName) + "/validate", {});
  }

  function checkPack(packName) {
    return postJson(API_BASE + "/packs/" + encodeURIComponent(packName) + "/check", {});
  }

  function previewPackInstall(packName) {
    return postJson(
      API_BASE + "/packs/" + encodeURIComponent(packName) + "/install/preview", {}
    );
  }

  function streamPackInstall(packName, preview, onProgress) {
    var url = API_BASE + "/packs/" + encodeURIComponent(packName) + "/install/stream";
    return SDK.authedFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
      body: JSON.stringify({ preview_digest: preview.preview_digest, confirm: true })
    }).then(function (response) {
      if (!response.ok) {
        return response.text().then(function (body) {
          throw new Error(response.status + ":" + body);
        });
      }
      if (!response.body || typeof response.body.getReader !== "function") {
        throw new Error("pack installation progress stream is unavailable");
      }
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      var result = null;

      function acceptLine(line) {
        if (!line.trim()) return;
        var event = JSON.parse(line);
        if (event.event === "progress") {
          onProgress(event);
          return;
        }
        if (event.event === "complete") {
          result = event.result;
          return;
        }
        if (event.event === "error") {
          var failure = new Error(event.error && event.error.message || "pack installation failed");
          failure.packInstall = event.error || null;
          throw failure;
        }
        throw new Error("pack installation returned an unknown event");
      }

      function readNext() {
        return reader.read().then(function (chunk) {
          buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
          var lines = buffer.split("\n");
          buffer = lines.pop();
          lines.forEach(acceptLine);
          if (!chunk.done) return readNext();
          acceptLine(buffer);
          if (!result) throw new Error("pack installation ended without a result");
          return result;
        });
      }

      return readNext();
    });
  }

  function packInstallFailure(reason) {
    if (reason && reason.packInstall) return reason.packInstall;
    var message = errorText(reason);
    var objectStart = message.indexOf("{");
    if (objectStart < 0) return null;
    try {
      var payload = JSON.parse(message.slice(objectStart));
      return payload && payload.detail && payload.detail.code === "pack_install_failed"
        ? payload.detail
        : null;
    } catch (_error) {
      return null;
    }
  }

  function previewPackSkillAction(packName, action, skillName) {
    var payload = { action: action };
    if (skillName) payload.skill = skillName;
    return postJson(
      API_BASE + "/packs/" + encodeURIComponent(packName) + "/skills/action/preview",
      payload
    );
  }

  function applyPackSkillAction(packName, preview) {
    var payload = {
      action: preview.action,
      preview_digest: preview.preview_digest,
      confirm: true
    };
    if (preview.skill_name) payload.skill = preview.skill_name;
    return postJson(
      API_BASE + "/packs/" + encodeURIComponent(packName) + "/skills/action",
      payload
    );
  }

  function buildWizardInventory() {
    return fetchJson(API_BASE + "/wizard/inventory").then(function (inventory) {
      var packs = inventory && Array.isArray(inventory.packs) ? inventory.packs : [];
      return Promise.all(packs.map(function (name) {
        return checkPack(name)
          .then(function (result) {
            var actions = result && Array.isArray(result.actions) ? result.actions : [];
            return {
              name: name,
              status: result && result.ready
                ? "ready"
                : actions.length
                  ? "installation required"
                  : "blocked"
            };
          })
          .catch(function () { return { name: name, status: "readiness unavailable" }; });
      })).then(function (packOptions) {
        inventory.pack_options = packOptions;
        return inventory;
      });
    });
  }

  function buildDispatcherReadiness() {
    return fetchJson(API_BASE + "/dispatcher-readiness");
  }

  function wizardReadiness(payload) {
    return postJson(API_BASE + "/wizard/readiness", payload);
  }

  function wizardPreview(payload) {
    return postJson(API_BASE + "/wizard/preview", payload);
  }

  function wizardStart(payload) {
    return postJson(API_BASE + "/wizard/start", payload);
  }

  function wizardLocalPreview(payload) {
    return postJson(API_BASE + "/wizard/local/preview", payload);
  }

  function wizardLocalStart(payload) {
    return postJson(API_BASE + "/wizard/local/start", payload);
  }

  function wizardBoardPreview(payload) {
    return postJson(API_BASE + "/wizard/boards/preview", payload);
  }

  function wizardCreateBoard(payload) {
    return postJson(API_BASE + "/wizard/boards", payload);
  }

  function buildPackSkillContent(packName, skillName) {
    return fetchJson(
      API_BASE + "/packs/" + encodeURIComponent(packName) +
      "/skills/" + encodeURIComponent(skillName)
    );
  }

  function buildWorkflows() {
    return fetchJson(API_BASE + "/workflows")
      .then(function (payload) {
        if (!payload || !Array.isArray(payload.workflows)) {
          return [];
        }
        return payload.workflows;
      })
      .catch(function () {
        return null;
      });
  }

  function buildConstraintSources() {
    return fetchJson(API_BASE + "/constraints/sources").then(function (payload) {
      return payload && Array.isArray(payload.sources) ? payload.sources : [];
    });
  }

  function buildConstraintSource(name) {
    return fetchJson(API_BASE + "/constraints/sources/" + encodeURIComponent(name));
  }

  function buildConstraintPrerequisites() {
    return fetchJson(API_BASE + "/prerequisites");
  }

  function buildWorkflowDetail(workflowId) {
    return fetchJson(API_BASE + "/workflows/" + encodeURIComponent(workflowId))
      .then(function (payload) {
        return payload;
      })
      .catch(function () {
        return null;
      });
  }

  function buildApprovalReview(workflowId) {
    return fetchJson(
      API_BASE + "/workflows/" + encodeURIComponent(workflowId) + "/approval-review"
    ).catch(function () {
      return { available: false };
    });
  }

  function buildReviewDecision(workflowId) {
    return fetchJson(
      API_BASE + "/workflows/" + encodeURIComponent(workflowId) + "/review-decision"
    ).catch(function () {
      return { available: false };
    });
  }

  function previewWorkflowDelivery(workflowId) {
    return postJson(
      API_BASE + "/workflows/" + encodeURIComponent(workflowId) + "/delivery/preview",
      {}
    );
  }

  function applyWorkflowDelivery(workflowId, previewDigest) {
    return postJson(
      API_BASE + "/workflows/" + encodeURIComponent(workflowId) + "/delivery",
      { preview_digest: previewDigest, confirm: true }
    );
  }

  function buildDecisions(workflowId) {
    return fetchJson(
      API_BASE + "/workflows/" + encodeURIComponent(workflowId) + "/decisions"
    )
      .then(function (payload) {
        if (!payload || !Array.isArray(payload.decisions)) {
          return { available: payload && payload.kanban_available === false, decisions: [] };
        }
        return {
          available: payload.kanban_available !== false,
          decisions: payload.decisions
        };
      })
      .catch(function () {
        return { available: false, decisions: [] };
      });
  }

  function buildDecisionCount() {
    return buildWorkflows().then(function (workflows) {
      if (workflows === null) return null;
      return Promise.all(workflows.map(function (workflow) {
        return buildDecisions(workflow.workflow_id);
      })).then(function (results) {
        return results.reduce(function (count, result) {
          return count + (result && Array.isArray(result.decisions)
            ? result.decisions.length
            : 0);
        }, 0);
      });
    });
  }

  function summarizeAction(action) {
    return action && action.rationale ? action.rationale : "";
  }

  function actionBadge(action) {
    var blockKind = action && action.blocker_kind ? action.blocker_kind : "";
    if (blockKind) {
      return "blocker: " + blockKind;
    }
    return action && action.action_kind ? action.action_kind.replace(/_/g, " ") : "";
  }

  function renderCardRow(card) {
    var cardClass = "daidala-card daidala-card-" + card.stage + " is-" + card.status;
    var blockReason = card.block_reason ? card.block_reason : "";
    var comments = Array.isArray(card.comments) ? card.comments.slice(-3) : [];
    var runs = Array.isArray(card.runs) ? card.runs.slice(-3) : [];
    var events = Array.isArray(card.events) ? card.events.slice(-5) : [];
    return createElement(
      "li",
      { key: card.task_id, className: cardClass, "data-testid": "daidala-card" },
      createElement("span", { className: "daidala-card-stage" }, card.stage),
      createElement("span", { className: "daidala-card-status" }, card.status),
      createElement("span", { className: "daidala-card-assignee" }, card.assignee || "—"),
      blockReason
        ? createElement("span", { className: "daidala-card-reason" }, blockReason)
        : null,
      runs.length
        ? createElement(
            "ul",
            { className: "daidala-card-history", "aria-label": "Run history" },
            runs.map(function (run) {
              return createElement(
                "li",
                { key: "run-" + run.id },
                (run.outcome || run.status || "active") + " · " + (run.profile || "unassigned"),
                run.summary ? createElement("span", null, " — " + run.summary) : null,
                run.error ? createElement("span", { className: "daidala-card-reason" }, " — " + run.error) : null
              );
            })
          )
        : null,
      comments.length
        ? createElement(
            "ul",
            { className: "daidala-card-history", "aria-label": "Recent comments" },
            comments.map(function (comment, index) {
              return createElement(
                "li",
                { key: "comment-" + index },
                (comment.author || "unknown") + ": " + (comment.body || "")
              );
            })
          )
        : null,
      events.length
        ? createElement(
            "p",
            { className: "daidala-card-events" },
            "Timeline: " + events.map(function (event) { return event.kind || "event"; }).join(" → ")
          )
        : null
    );
  }

  function renderDecisionItem(action) {
    return createElement(
      "li",
      {
        key: action.action_kind + (action.card_id || ""),
        className: "daidala-decision daidala-decision-" + action.action_kind,
        "data-testid": "daidala-decision"
      },
      createElement("span", { className: "daidala-decision-kind" }, actionBadge(action)),
      createElement("span", { className: "daidala-decision-rationale" }, summarizeAction(action)),
      action.card_id
        ? createElement(
            "span",
            { className: "daidala-decision-card" },
            "card " + action.card_id
          )
        : null
    );
  }

  function renderRecommendationItem(action) {
    return createElement(
      "li",
      { key: action.action_kind + (action.card_id || ""), className: "daidala-recommendation" },
      createElement("strong", null, actionBadge(action)),
      createElement("span", null, summarizeAction(action))
    );
  }

  function WorkflowApproval(props) {
    var packet = props.packet;
    var plan = packet && packet.plan;
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var submittingState = useState(false);
    var submitting = submittingState[0];
    var setSubmitting = submittingState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];

    if (!packet || packet.available === false || !plan) {
      return createElement(
        "p",
        { className: "daidala-workflow-unavailable", "data-testid": "daidala-plan-unavailable" },
        "Plan unavailable"
      );
    }

    function approveExactPlan() {
      setSubmitting(true);
      setMessage("");
      postJson(
        API_BASE + "/workflows/" + encodeURIComponent(packet.workflow_id) + "/approve",
        {
          artifact_id: plan.artifact_id,
          plan_digest: plan.plan_digest,
          summary_digest: plan.summary_digest,
          confirm: true
        }
      ).then(function () {
        setConfirmed(false);
        setMessage("Exact plan approved.");
        props.onApproved();
      }).catch(function (error) {
        setMessage(error.message);
      }).finally(function () {
        setSubmitting(false);
      });
    }

    return createElement(
      "section",
      { className: "daidala-approval", "data-testid": "daidala-approval-packet" },
      createElement("h4", { className: "daidala-workflow-section-title" }, "Exact plan approval"),
      createElement("p", { className: "daidala-approval-headline" }, plan.summary.headline),
      createElement(
        "dl",
        { className: "daidala-workflow-identity" },
        createElement("div", null, createElement("dt", null, "workflow"), createElement("dd", null, packet.tuple.workflow_id)),
        createElement("div", null, createElement("dt", null, "policy revision"), createElement("dd", null, String(packet.tuple.policy_revision))),
        createElement("div", null, createElement("dt", null, "plan revision"), createElement("dd", null, String(packet.tuple.plan_revision))),
        createElement("div", null, createElement("dt", null, "plan digest"), createElement("dd", null, plan.plan_digest)),
        createElement("div", null, createElement("dt", null, "artifact ID"), createElement("dd", null, plan.artifact_id)),
        createElement("div", null, createElement("dt", null, "summary digest"), createElement("dd", null, plan.summary_digest)),
        createElement("div", null, createElement("dt", null, "constraint revision"), createElement("dd", null, String(packet.tuple.constraints_revision === null ? "none" : packet.tuple.constraints_revision))),
        createElement("div", null, createElement("dt", null, "constraint digest"), createElement("dd", null, packet.tuple.constraints_digest || "none")),
        createElement("div", null, createElement("dt", null, "pack revision"), createElement("dd", null, packet.pack_identity.source_revision)),
        createElement("div", null, createElement("dt", null, "verification"), createElement("dd", null, plan.verification_state))
      ),
      createElement("h5", null, "Changes"),
      createElement("ul", null, plan.summary.changes.map(function (item) { return createElement("li", { key: item }, item); })),
      createElement("h5", null, "Risks"),
      plan.summary.risks.length
        ? createElement("ul", null, plan.summary.risks.map(function (item) { return createElement("li", { key: item }, item); }))
        : createElement("p", null, "No risks recorded."),
      createElement("h5", null, "Verification"),
      createElement("ul", null, plan.summary.verification.map(function (item) { return createElement("li", { key: item }, item); })),
      createElement("details", null,
        createElement("summary", null, "Read exact plan text"),
        createElement("pre", { className: "daidala-plan-text" }, plan.content)
      ),
      createElement("p", { className: "daidala-approval-consequences" },
        "Consequences: " + packet.consequences.worktree + " · next cards " +
        packet.consequences.next_cards.join(" → ") + " · commit false · push false"
      ),
      createElement(
        "section",
        { className: "daidala-next-packet", "data-testid": "daidala-next-packet" },
        createElement("h5", null, "What the next card receives"),
        createElement("p", null,
          packet.successor_packet.stage + " · policy " + packet.successor_packet.policy_revision +
          " · plan " + packet.successor_packet.plan_revision + " · " +
          packet.successor_packet.plan_digest
        ),
        createElement("ul", null,
          packet.successor_packet.activations.map(function (activation) {
            return createElement("li", { key: "activation-" + activation.stage }, "activation " + activation.stage + " · " + activation.digest);
          }),
          packet.successor_packet.artifacts.map(function (artifact) {
            return createElement("li", { key: "artifact-" + artifact.stage }, "artifact " + artifact.stage + " · " + artifact.digest);
          })
        ),
        packet.successor_packet.baseline_commit
          ? createElement("p", { className: "daidala-post-approval" },
              "Baseline " + packet.successor_packet.baseline_commit + " · worktree " +
              (packet.successor_packet.worktree.present ? "present" : "not created")
            )
          : null
      ),
      packet.approval
        ? createElement("p", { className: "daidala-banner" }, "This exact plan is approved.")
        : createElement(React.Fragment, null,
            createElement("label", { className: "daidala-confirm" },
              createElement("input", {
                type: "checkbox",
                checked: confirmed,
                onChange: function (event) { setConfirmed(event.target.checked); }
              }),
              "I reviewed this exact plan"
            ),
            createElement("button", {
              type: "button",
              className: "daidala-refresh",
              disabled: !confirmed || submitting,
              onClick: approveExactPlan
            }, submitting ? "Approving…" : "Approve exact plan")
          ),
      message ? createElement("p", { role: "status", className: "daidala-banner" }, message) : null
    );
  }

  function reviewActionLabel(action) {
    if (action === "accept_delivery") return "Accept and continue to delivery";
    if (action === "request_revision") return "Request revision";
    return "Reject workflow";
  }

  function WorkflowReviewDisposition(props) {
    var packet = props.packet;
    var review = packet && packet.review;
    var evidence = packet && packet.evidence;
    var actions = packet && Array.isArray(packet.allowed_actions) ? packet.allowed_actions : [];
    var actionState = useState(actions[0] || "request_revision");
    var action = actionState[0];
    var setAction = actionState[1];
    var rationaleState = useState("");
    var rationale = rationaleState[0];
    var setRationale = rationaleState[1];
    var previewState = useState(null);
    var preview = previewState[0];
    var setPreview = previewState[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];

    if (!packet || packet.available === false) return null;
    if (!review || !evidence) {
      return packet.pending_revision_request
        ? createElement("section", { className: "daidala-review", "data-testid": "daidala-review-decision" },
            createElement("h4", { className: "daidala-workflow-section-title" }, "Successor plan pending"),
            createElement("p", null,
              "Plan revision " + packet.pending_revision_request.target_plan_revision +
              " must be recorded and freshly approved before implementation."
            )
          )
        : null;
    }

    function resetDecision(nextAction, nextRationale) {
      setAction(nextAction);
      setRationale(nextRationale);
      setPreview(null);
      setConfirmed(false);
      setMessage("");
    }

    function previewDecision() {
      setBusy(true);
      setMessage("");
      postJson(
        API_BASE + "/workflows/" + encodeURIComponent(packet.workflow_id) +
        "/review-disposition/preview",
        { action: action, rationale: rationale }
      ).then(function (result) {
        setPreview(result);
        setConfirmed(false);
      }).catch(function (error) {
        setPreview(null);
        setMessage(error.message);
      }).finally(function () {
        setBusy(false);
      });
    }

    function applyDecision() {
      if (!preview || !confirmed) return;
      setBusy(true);
      setMessage("");
      postJson(
        API_BASE + "/workflows/" + encodeURIComponent(packet.workflow_id) +
        "/review-disposition",
        {
          action: action,
          review_digest: packet.review_digest,
          preview_digest: preview.preview_digest,
          rationale: rationale,
          confirm: true
        }
      ).then(function (result) {
        setConfirmed(false);
        setPreview(null);
        if (action === "request_revision" && result.workflow) {
          var target = "/daidala?workflow=" + encodeURIComponent(packet.workflow_id) +
            "&decision=plan-approval&plan_revision=" + result.workflow.plan_revision;
          window.history.pushState({}, "", target);
          window.dispatchEvent(new PopStateEvent("popstate"));
          setMessage("Revision requested. Opening successor exact-plan approval.");
        } else {
          setMessage("Review disposition recorded.");
        }
        props.onDecided(result);
      }).catch(function (error) {
        setMessage(error.message);
      }).finally(function () {
        setBusy(false);
      });
    }

    var summary = evidence.change_summary;
    var implementation = evidence.implementation;
    var findings = Array.isArray(review.findings) ? review.findings : [];
    var tuple = packet.exact_tuple;
    return createElement(
      "section",
      {
        id: "daidala-review-decision",
        className: "daidala-review",
        "data-testid": "daidala-review-decision"
      },
      createElement("h4", { className: "daidala-workflow-section-title" }, "Human review disposition"),
      createElement("p", { className: "daidala-approval-headline" }, summary.headline),
      createElement("p", { className: "daidala-review-digest" }, "Review digest " + packet.review_digest),
      createElement("p", { className: "daidala-review-digest" }, "Summary digest " + evidence.summary_digest),
      createElement("h5", null, "Captured changes"),
      createElement("ul", null, summary.changes.map(function (item) {
        return createElement("li", { key: item }, item);
      })),
      createElement("h5", null, "Changed paths"),
      createElement("ul", null, implementation.changed_paths.map(function (path) {
        return createElement("li", { key: path }, path);
      })),
      createElement("details", null,
        createElement("summary", null, "Read exact captured diff"),
        createElement("pre", { className: "daidala-review-diff" }, implementation.content)
      ),
      createElement("h5", null, "Verification evidence"),
      createElement("ul", null, evidence.verification.map(function (row) {
        return createElement("li", { key: row.output_digest },
          row.command + " · exit " + row.exit_code + " · " + row.output_digest
        );
      })),
      createElement("h5", null, "Reviewer outcome · " + review.outcome),
      findings.length
        ? createElement("ul", null, findings.map(function (finding) {
            return createElement("li", { key: finding.id },
              finding.severity + (finding.blocking ? " · blocking · " : " · ") +
              finding.title + " — " + finding.rationale
            );
          }))
        : createElement("p", null, "No findings recorded."),
      createElement("dl", { className: "daidala-workflow-identity" },
        Object.keys(tuple).map(function (key) {
          var value = tuple[key];
          return createElement("div", { key: key },
            createElement("dt", null, key.replace(/_/g, " ")),
            createElement("dd", null, Array.isArray(value) ? value.join(", ") : String(value === null ? "none" : value))
          );
        })
      ),
      createElement("h5", null, "Fixed consequences"),
      createElement("p", null, packet.consequences[action] || "Select an attended action."),
      preview && preview.successor_packet
        ? createElement("section", { className: "daidala-next-packet", "data-testid": "daidala-review-successor-packet" },
            createElement("h5", null, "What the successor Plan card receives"),
            createElement("p", null,
              "Plan revision " + preview.successor_packet.target_plan_revision +
              " · source review " + preview.successor_packet.source_review.digest
            ),
            createElement("p", null,
              "Implementation " + preview.successor_packet.source_implementation.digest +
              " · feedback " + preview.successor_packet.normalized_feedback
            )
          )
        : action === "request_revision"
          ? createElement("p", null, "Preview to inspect the exact successor packet before confirmation.")
          : null,
      packet.disposition
        ? createElement("p", { className: "daidala-banner" },
            "Disposition recorded: " + packet.disposition.action + " · " + packet.disposition.decided_at
          )
        : createElement(React.Fragment, null,
            createElement("label", { className: "daidala-wizard-field" },
              createElement("span", null, "Attended action"),
              createElement("select", {
                value: action,
                onChange: function (event) { resetDecision(event.target.value, rationale); }
              }, actions.map(function (item) {
                return createElement("option", { key: item, value: item }, reviewActionLabel(item));
              }))
            ),
            createElement("label", { className: "daidala-wizard-field" },
              createElement("span", null, action === "request_revision" ? "Required revision feedback" : "Required rationale"),
              createElement("textarea", {
                value: rationale,
                rows: 4,
                maxLength: 4096,
                onChange: function (event) { resetDecision(action, event.target.value); }
              })
            ),
            createElement("button", {
              type: "button",
              disabled: busy || !rationale.trim(),
              onClick: previewDecision
            }, busy ? "Previewing…" : "Preview review disposition"),
            preview
              ? createElement(React.Fragment, null,
                  createElement("p", null, "Preview digest " + preview.preview_digest),
                  createElement("p", null,
                    preview.cards_to_archive.length + " post-gate card(s) archived · owned worktree release " +
                    (preview.owned_worktree_release ? "yes" : "no")
                  ),
                  createElement("label", { className: "daidala-confirm" },
                    createElement("input", {
                      type: "checkbox",
                      checked: confirmed,
                      onChange: function (event) { setConfirmed(event.target.checked); }
                    }),
                    "I confirm applying this exact review disposition"
                  ),
                  createElement("button", {
                    type: "button",
                    disabled: busy || !confirmed,
                    onClick: applyDecision
                  }, busy ? "Applying…" : reviewActionLabel(action))
                )
              : null
          ),
      review.outcome !== "accepted"
        ? createElement("p", { className: "daidala-workflow-meta" },
            "Challenge reviewer uses public Kanban comment and unblock controls; it never overrides this policy gate."
          )
        : null,
      message ? createElement("p", { role: "status", className: "daidala-banner" }, message) : null
    );
  }

  function WorkflowDelivery(props) {
    var packet = props.packet;
    var disposition = packet && packet.disposition;
    var previewState = useState(null);
    var preview = previewState[0];
    var setPreview = previewState[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];
    var completed = props.completed;

    if (!packet || packet.available === false || !disposition || disposition.action !== "accept_delivery") {
      return null;
    }

    function requestPreview() {
      setBusy(true);
      setMessage("");
      previewWorkflowDelivery(props.workflowId).then(function (next) {
        setPreview(next);
        setConfirmed(false);
      }).catch(function (error) {
        setPreview(null);
        setMessage(error.message);
      }).finally(function () {
        setBusy(false);
      });
    }

    function applyPreview() {
      if (!preview || !preview.credential_available || !confirmed) return;
      setBusy(true);
      setMessage("");
      applyWorkflowDelivery(props.workflowId, preview.preview_digest).then(function (result) {
        setPreview(null);
        setConfirmed(false);
        setMessage("Branch delivery completed: " + result.branch + " · " + result.commit);
        props.onDelivered();
      }).catch(function (error) {
        setMessage(error.message);
      }).finally(function () {
        setBusy(false);
      });
    }

    if (completed) {
      return createElement(
        "section",
        { className: "daidala-delivery", "data-testid": "daidala-delivery" },
        createElement("h4", { className: "daidala-workflow-section-title" }, "Branch delivery"),
        createElement("p", { className: "daidala-banner" }, "Branch delivery is recorded."),
        completed.branch
          ? createElement("p", null, "Branch " + completed.branch + " · commit " + (completed.commit || "recorded"))
          : null
      );
    }

    return createElement(
      "section",
      { className: "daidala-delivery", "data-testid": "daidala-delivery" },
      createElement("h4", { className: "daidala-workflow-section-title" }, "Branch delivery"),
      createElement("p", null, "Review the exact branch-delivery preview before confirming the commit and push."),
      !preview
        ? createElement("button", {
            type: "button", disabled: busy, onClick: requestPreview
          }, busy ? "Previewing…" : "Preview branch delivery")
        : createElement(React.Fragment, null,
            createElement("dl", { className: "daidala-workflow-identity" },
              createElement("div", null, createElement("dt", null, "branch"), createElement("dd", null, preview.branch)),
              createElement("div", null, createElement("dt", null, "baseline commit"), createElement("dd", null, preview.baseline_commit)),
              createElement("div", null, createElement("dt", null, "review digest"), createElement("dd", null, preview.review_digest)),
              createElement("div", null, createElement("dt", null, "delivery credential"), createElement("dd", null, preview.credential_available ? "available" : "unavailable")),
              createElement("div", null, createElement("dt", null, "preview digest"), createElement("dd", null, preview.preview_digest))
            ),
            createElement("h5", null, "Reviewed changed paths"),
            createElement("ul", null, preview.changed_paths.map(function (path) {
              return createElement("li", { key: path }, path);
            })),
            !preview.credential_available
              ? createElement("p", { className: "daidala-banner daidala-banner-warning" }, "Delivery credential unavailable. Configure the mounted Hermes profile outside Daidala, then request a fresh preview.")
              : createElement(React.Fragment, null,
                  createElement("label", { className: "daidala-confirm" },
                    createElement("input", {
                      type: "checkbox",
                      checked: confirmed,
                      onChange: function (event) { setConfirmed(event.target.checked); }
                    }),
                    "I confirm committing and pushing this exact branch delivery"
                  ),
                  createElement("button", {
                    type: "button",
                    disabled: busy || !confirmed,
                    onClick: applyPreview
                  }, busy ? "Delivering…" : "Confirm commit and push branch")
                )
          ),
      message ? createElement("p", { role: "status", className: "daidala-banner" }, message) : null
    );
  }

  function renderTimeline(detail) {
    var timeline = detail && Array.isArray(detail.timeline) ? detail.timeline : [];
    return createElement(
      "ol",
      { className: "daidala-timeline", "data-testid": "daidala-timeline" },
      timeline.map(function (row) {
        var label = row.kind === "approval_gate"
          ? "Human approval — Daidala policy gate"
          : row.kind === "review_gate"
            ? "Human review disposition — Daidala policy gate"
            : row.label;
        var props = {
          key: row.kind + "-" + row.stage,
          className: "daidala-timeline-row is-" + row.status
        };
        if (row.kind === "approval_gate") {
          props.className += " daidala-approval-gate";
          props["data-testid"] = "daidala-approval-gate";
        }
        if (row.kind === "review_gate") {
          props.className += " daidala-review-gate";
          props["data-testid"] = "daidala-review-gate";
        }
        return createElement(
          "li",
          props,
          row.kind === "approval_gate" && !row.approval
            ? createElement("a", { href: "#daidala-decision-panel" }, label)
            : row.kind === "review_gate" && !row.disposition
              ? createElement("a", { href: "#daidala-review-decision" }, label)
            : createElement("strong", null, label),
          createElement("span", null, row.status),
          row.kind === "approval_gate" && row.approval
            ? createElement("span", null, row.approval.plan_digest + " · " + row.approval.decided_at)
            : row.kind === "review_gate" && row.disposition
              ? createElement("span", null, row.review_digest + " · " + row.disposition.decided_at)
            : null
        );
      })
    );
  }

  function BlockedCardRemediation(props) {
    var card = props.card;
    var recommendation = props.recommendation;
    var blockerKind = card.block_kind ||
      (recommendation && recommendation.blocker_kind) || "needs_input";
    var requestedRemediation = (recommendation && recommendation.rationale) ||
      card.block_reason || "No structured remediation was supplied.";
    var textState = useState("");
    var text = textState[0];
    var setText = textState[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];
    var comments = Array.isArray(card.comments) ? card.comments.slice(-3) : [];
    var runs = Array.isArray(card.runs) ? card.runs.slice(-3) : [];

    function submit(action) {
      if (!text.trim() || !confirmed) return;
      setBusy(true);
      setMessage("");
      var endpoint = API_BASE + "/workflows/" + encodeURIComponent(props.workflowId) +
        "/cards/" + encodeURIComponent(card.task_id) +
        (action === "comment" ? "/comment" : "/unblock");
      var payload = { confirm: true };
      payload[action === "comment" ? "comment" : "reason"] = text;
      postJson(endpoint, payload).then(function () {
        setText("");
        setConfirmed(false);
        setMessage(action === "comment" ? "Remediation comment recorded." : "Card unblocked for retry.");
        props.onChanged();
      }).catch(function (error) {
        setMessage(error.message);
      }).finally(function () {
        setBusy(false);
      });
    }

    return createElement(
      "section",
      { className: "daidala-remediation", "data-testid": "daidala-card-remediation" },
      createElement("h5", null, "Blocked card"),
      createElement("p", null, "Stage: " + card.stage),
      createElement("h5", null, "Blocker kind"),
      createElement("p", null, blockerKind),
      createElement("h5", null, "Requested remediation"),
      createElement("p", null, requestedRemediation),
      createElement("h5", null, "Latest relevant evidence"),
      comments.length || runs.length
        ? createElement("ul", null,
            comments.map(function (row, index) {
              return createElement("li", { key: "comment-" + index },
                (row.author || "operator") + ": " + (row.body || "")
              );
            }),
            runs.map(function (row, index) {
              return createElement("li", { key: "run-" + index },
                (row.outcome || row.status || "run") +
                (row.summary ? " — " + row.summary : row.error ? " — " + row.error : "")
              );
            })
          )
        : createElement("p", null, "No recent card evidence is available."),
      createElement("label", { className: "daidala-wizard-field" },
        createElement("span", null, "Remediation evidence"),
        createElement("input", {
          value: text,
          maxLength: 500,
          onChange: function (event) { setText(event.target.value); setConfirmed(false); }
        })
      ),
      createElement("label", { className: "daidala-confirm" },
        createElement("input", {
          type: "checkbox",
          checked: confirmed,
          onChange: function (event) { setConfirmed(event.target.checked); }
        }),
        "I confirm this remediation action"
      ),
      createElement("div", { className: "daidala-remediation-actions" },
        createElement("button", {
          type: "button", disabled: busy || !text.trim() || !confirmed,
          onClick: function () { submit("comment"); }
        }, busy ? "Recording…" : "Comment remediation"),
        createElement("button", {
          type: "button", disabled: busy || !text.trim() || !confirmed,
          onClick: function () { submit("unblock"); }
        }, busy ? "Unblocking…" : "Unblock for retry")
      ),
      message ? createElement("p", { role: "status", className: "daidala-banner" }, message) : null
    );
  }

  function WorkflowCancellation(props) {
    var reasonState = useState("");
    var reason = reasonState[0];
    var setReason = reasonState[1];
    var previewState = useState(null);
    var preview = previewState[0];
    var setPreview = previewState[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];
    var cards = preview && Array.isArray(preview.cards) ? preview.cards : [];

    function previewCancellation() {
      if (!reason.trim()) return;
      setBusy(true);
      setMessage("");
      postJson(API_BASE + "/workflows/" + encodeURIComponent(props.workflowId) + "/cancel/preview", {
        reason: reason
      }).then(function (result) {
        setPreview(result);
        setConfirmed(false);
      }).catch(function (error) {
        setPreview(null);
        setMessage(error.message);
      }).finally(function () { setBusy(false); });
    }

    function cancelWorkflow() {
      if (!preview || !confirmed) return;
      setBusy(true);
      setMessage("");
      postJson(API_BASE + "/workflows/" + encodeURIComponent(props.workflowId) + "/cancel", {
        reason: reason,
        preview_digest: preview.preview_digest,
        confirm: true
      }).then(function () {
        setPreview(null);
        setConfirmed(false);
        setMessage("Workflow cancelled.");
        props.onCancelled();
      }).catch(function (error) {
        setMessage(error.message);
      }).finally(function () { setBusy(false); });
    }

    return createElement(
      "section",
      { className: "daidala-cancellation", "data-testid": "daidala-workflow-cancellation" },
      createElement("h4", { className: "daidala-workflow-section-title" }, "Cancel workflow"),
      createElement("p", null, "Cancellation archives workflow cards and releases only a Daidala-owned worktree."),
      createElement("label", { className: "daidala-wizard-field" },
        createElement("span", null, "Cancellation reason"),
        createElement("input", {
          value: reason,
          maxLength: 500,
          onChange: function (event) { setReason(event.target.value); setPreview(null); setConfirmed(false); }
        })
      ),
      createElement("button", {
        type: "button", disabled: busy || !reason.trim(), onClick: previewCancellation
      }, busy ? "Previewing…" : "Preview cancellation"),
      preview ? createElement("div", { className: "daidala-cancellation-preview" },
        createElement("h5", null, "Affected cards"),
        cards.length
          ? createElement("ul", null, cards.map(function (card) {
              return createElement("li", { key: card.task_id }, card.stage + " · " + card.task_id);
            }))
          : createElement("p", null, "No workflow cards are recorded."),
        createElement("p", null,
          preview.owned_worktree_release
            ? "Daidala-owned worktree will be released."
            : "No Daidala-owned worktree will be released."
        ),
        createElement("label", { className: "daidala-confirm" },
          createElement("input", {
            type: "checkbox", checked: confirmed,
            onChange: function (event) { setConfirmed(event.target.checked); }
          }),
          "I confirm cancelling this workflow"
        ),
        createElement("button", {
          type: "button", disabled: busy || !confirmed, onClick: cancelWorkflow
        }, busy ? "Cancelling…" : "Cancel workflow")
      ) : null,
      message ? createElement("p", { role: "status", className: "daidala-banner" }, message) : null
    );
  }

  function renderCardAudit(cards, workflowId, onChanged, recommendations) {
    return createElement(
      "details",
      { className: "daidala-card-audit" },
      createElement("summary", null, "Live Kanban and audit detail"),
      cards.length === 0
        ? createElement("p", { className: "daidala-workflow-empty" }, "No cards yet")
        : createElement(
            "ul",
            { className: "daidala-workflow-cards", "data-testid": "daidala-cards" },
            cards.map(renderCardRow)
            ),
            cards.filter(function (card) { return card.status === "blocked"; }).map(function (card) {
            var recommendation = recommendations.filter(function (candidate) {
              return candidate.card_id === card.task_id;
            })[0] || null;
            return createElement(BlockedCardRemediation, {
            key: card.task_id, card: card, recommendation: recommendation,
            workflowId: workflowId, onChanged: onChanged
            });
            })
            );
            }

  function renderWorkflowCard(
    workflow, detail, decisions, approvalReview, reviewDecision, dispatcher, onApproved, onReviewDecided
  ) {
    var summary = detail && detail.workflow ? detail.workflow : workflow;
    var policyRevision = summary.policy_revision;
    var planRevision = summary.plan_revision;
    var approval = summary.approval;
    var archived = summary.lifecycle_status === "archived";
    var cards = detail && detail.kanban && Array.isArray(detail.kanban.cards)
      ? detail.kanban.cards
      : [];
    var decisionsList = decisions && decisions.decisions
      ? decisions.decisions
      : [];
    var recommendations = detail && Array.isArray(detail.recommendations)
      ? detail.recommendations
      : [];
    var gatewayBlockedCards = dispatcher && Array.isArray(dispatcher.gateway_blocked_cards)
      ? dispatcher.gateway_blocked_cards.filter(function (row) {
        return row.workflow_id === summary.workflow_id;
      })
      : [];


    return createElement(
      "article",
      {
        className: "daidala-workflow",
        key: summary.workflow_id,
        "data-testid": "daidala-workflow",
        "data-workflow-id": summary.workflow_id
      },
      createElement(
        "header",
        { className: "daidala-workflow-header" },
        createElement("h3", { className: "daidala-workflow-title" }, summary.workflow_id),
        createElement(
          "p",
          { className: "daidala-workflow-meta" },
          summary.board_slug + " · " + summary.pack_name + " · policy " + policyRevision
        ),
        archived
          ? createElement(
              "p",
              { className: "daidala-workflow-meta", "data-testid": "daidala-workflow-archived" },
              "Archived workflow"
            )
          : null
      ),
      gatewayBlockedCards.map(function (blocker) {
        return createElement(
          "p",
          {
            key: blocker.task_id,
            role: "alert",
            className: "daidala-banner daidala-banner-error",
            "data-testid": "daidala-workflow-gateway-error"
          },
          "Ready " + blocker.stage + " card " + blocker.task_id + " is assigned to "
            + blocker.profile + ", but its worker gateway is " + blocker.gateway_status
            + ". This workflow cannot dispatch the card. Check it with hermes -p "
            + blocker.profile + " gateway status, then start it with hermes -p "
            + blocker.profile + " gateway start."
        );
      }),
      createElement(
        "p",
        { className: "daidala-workflow-goal" },
        summary.requested_goal || ""
      ),
      createElement(
        "dl",
        { className: "daidala-workflow-identity" },
        createElement(
          "div",
          null,
          createElement("dt", null, "policy revision"),
          createElement("dd", null, String(policyRevision))
        ),
        createElement(
          "div",
          null,
          createElement("dt", null, "plan revision"),
          createElement("dd", null, String(planRevision))
        ),
        archived
          ? null
          : createElement(
              "div",
              null,
              createElement("dt", null, "approval"),
              createElement(
                "dd",
                null,
                approval ? "recorded" : "pending"
              )
            ),
        summary.current_constraints_digest
          ? createElement(
              "div",
              null,
              createElement("dt", null, "constraint digest"),
              createElement(
                "dd",
                { className: "daidala-workflow-digest" },
                summary.current_constraints_digest
              )
            )
          : null
      ),
      archived
        ? createElement(
            "p",
            { className: "daidala-workflow-empty" },
            "Archived workflows have no pending human decision."
          )
        : decisions === undefined
        ? createElement(
            "p",
            { className: "daidala-workflow-loading" },
            "Loading decisions"
          )
        : !decisions.available
          ? createElement(
              "p",
              { className: "daidala-workflow-unavailable" },
              "Live Kanban state unavailable"
            )
          : decisionsList.length === 0
            ? createElement("p", { className: "daidala-workflow-empty" }, "No pending human decision")
            : createElement(
                "section",
                {
                  id: "daidala-decision-panel",
                  className: "daidala-decision-panel",
                  "data-testid": "daidala-decision-panel"
                },
                createElement("h4", { className: "daidala-workflow-section-title" }, "Needs your decision"),
                createElement(
                  "ul",
                  { className: "daidala-workflow-decisions", "data-testid": "daidala-decisions" },
                  decisionsList.map(renderDecisionItem)
                ),
                approvalReview === undefined
                  ? createElement("p", { className: "daidala-workflow-loading" }, "Loading approval evidence")
                  : createElement(WorkflowApproval, { packet: approvalReview, onApproved: onApproved })
              ),
      archived
        ? null
        : reviewDecision === undefined
        ? createElement("p", { className: "daidala-workflow-loading" }, "Loading review evidence")
        : createElement(WorkflowReviewDisposition, {
            packet: reviewDecision,
            onDecided: onReviewDecided
          }),
      archived
        ? null
        : createElement(WorkflowDelivery, {
            workflowId: summary.workflow_id,
            packet: reviewDecision,
            completed: summary.committed && summary.pushed ? summary.delivery_authorization : null,
            onDelivered: onApproved
          }),
      createElement(
        "h4",
        { className: "daidala-workflow-section-title" },
        "Recommended next actions"
      ),
      recommendations.length
        ? createElement(
            "ul",
            { className: "daidala-recommendations", "data-testid": "daidala-recommendations" },
            recommendations.map(renderRecommendationItem)
          )
        : createElement("p", { className: "daidala-workflow-empty" }, "No recommendation available"),
      createElement(
        "h4",
        { className: "daidala-workflow-section-title" },
        "Stage timeline"
      ),
      renderTimeline(detail),
      detail === undefined
        ? createElement(
            "p",
            { className: "daidala-workflow-loading" },
            "Loading card status"
          )
        : detail === null || (detail.kanban && detail.kanban.available === false)
          ? createElement(
              "p",
              { className: "daidala-workflow-unavailable" },
              "Live Kanban state unavailable"
            )
          : renderCardAudit(cards, summary.workflow_id, onApproved, recommendations),
      detail && detail.workflow
        ? createElement(WorkflowCancellation, {
            workflowId: summary.workflow_id,
            onCancelled: onApproved
          })
        : null,
      null
    );
  }

  function ConstraintEditor(props) {
    var initial = props.constraints ? props.constraints.canonical_content : "";
    var contentState = useState(initial);
    var content = contentState[0];
    var setContent = contentState[1];
    var inputModeState = useState("draft");
    var inputMode = inputModeState[0];
    var setInputMode = inputModeState[1];
    var previewState = useState(null);
    var preview = previewState[0];
    var setPreview = previewState[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];
    var currentDigest = props.workflow.current_constraints_digest || null;
    var isCreate = currentDigest === null;
    var source = props.source && props.source.available ? props.source : null;
    var sourceIdentity = source ? source.source : null;
    var template = props.template && props.template.content ? props.template.content : "";
    var limits = props.schemaLimits || {};

    function invalidate() {
      setPreview(null);
      setConfirmed(false);
      setMessage("");
    }

    function payload() {
      var request = {
        workflow_id: props.workflow.workflow_id,
        expected_current_digest: currentDigest
      };
      if (inputMode === "reference" && sourceIdentity) {
        request.constraints_skill = sourceIdentity.name;
        request.constraints_skill_digest = sourceIdentity.digest;
      } else {
        request.constraints_content = content;
      }
      return request;
    }

    function previewChange() {
      postJson(API_BASE + "/constraints/preview", payload()).then(function (value) {
        setPreview(value);
        setConfirmed(false);
        setMessage(value.valid ? "Preview ready." : value.errors.join("; "));
      }).catch(function (error) { setMessage(error.message); });
    }

    function replaceConstraints() {
      if (!preview || !preview.valid || preview.current_digest !== currentDigest || !confirmed) return;
      postJson(API_BASE + "/constraints/replace", Object.assign({}, payload(), { confirm: true }))
        .then(function () {
          setMessage((isCreate ? "Constraints created." : "Constraints replaced.") + " Fresh approval is required.");
          setPreview(null);
          setConfirmed(false);
          if (props.onApplied) props.onApplied();
        })
        .catch(function (error) { setMessage(error.message); });
    }

    return createElement("section", { className: "daidala-constraints", "data-testid": "daidala-constraints" },
      createElement("h3", null, isCreate ? "New workflow constraints" : "Edit workflow constraints"),
      createElement("p", { className: "daidala-workflow-meta" },
        "Authority: " + (isCreate ? "create with null current digest" : "replace displayed current digest") +
        " · revision " + (props.constraints ? props.constraints.revision : "none") +
        " · digest " + (currentDigest || "none")
      ),
      createElement("p", { className: "daidala-workflow-meta" },
        "Limits: global " + (limits.global_max || "?") + " · phase " + (limits.phase_max || "?") +
        " · item " + (limits.constraint_bytes || "?") + " bytes · canonical " +
        (limits.canonical_bytes || "?") + " bytes · worker card body 8192 characters"
      ),
      createElement("div", { className: "daidala-config-actions" },
        createElement("button", { type: "button", onClick: function () { setContent(template); setInputMode("draft"); invalidate(); } }, "Insert schema skeleton"),
        source ? createElement("button", { type: "button", onClick: function () { setContent(source.canonical_content); setInputMode("draft"); invalidate(); } }, "Copy selected template into draft") : null,
        source ? createElement("button", { type: "button", onClick: function () { setInputMode("reference"); invalidate(); } }, "Use as reference skill") : null
      ),
      sourceIdentity ? createElement("p", { className: "daidala-workflow-meta" },
        "Selected source " + sourceIdentity.name + " · digest " + sourceIdentity.digest + " · mode " + inputMode
      ) : null,
      createElement("textarea", {
        value: content,
        disabled: inputMode === "reference",
        onChange: function (event) { setContent(event.target.value); setInputMode("draft"); invalidate(); },
        rows: 10,
        "aria-label": "Complete workflow constraints YAML"
      }),
      createElement("button", { type: "button", onClick: previewChange }, "Preview constraint change"),
      preview && preview.errors && preview.errors.length
        ? createElement("p", { className: "daidala-banner daidala-banner-error" }, preview.errors.join("; "))
        : null,
      preview && preview.canonical_content
        ? createElement("pre", { className: "daidala-constraint-canonical" }, preview.canonical_content)
        : null,
      preview && preview.valid
        ? createElement("p", { className: "daidala-workflow-meta" },
            "Preview digest " + preview.new_digest + " · canonical bytes " +
            String(new TextEncoder().encode(preview.canonical_content || "").length) + " · " +
            (preview.impact.graph_recreated
              ? "semantic change: approval, worktree, evidence, and current cards will be invalidated"
              : "no semantic change")
          )
        : null,
      preview && preview.valid && !preview.impact.graph_recreated
        ? createElement("p", null, "No semantic change; replacement is unnecessary.")
        : null,
      preview && preview.valid && preview.impact.graph_recreated
        ? createElement("label", null,
            createElement("input", { type: "checkbox", checked: confirmed, onChange: function (event) { setConfirmed(event.target.checked); } }),
            "I understand approval, worktree, evidence, and cards are invalidated"
          )
        : null,
      preview && preview.valid && preview.impact.graph_recreated
        ? createElement("button", { type: "button", disabled: !confirmed, onClick: replaceConstraints }, isCreate ? "Create constraints" : "Apply replacement")
        : null,
      message ? createElement("p", { role: "status" }, message) : null
    );
  }

  function useVisiblePolling(intervalMs, loader) {
    var timerRef = useRef(null);
    var stateRef = useRef({ snapshot: undefined, error: undefined });
    var counterRef = useRef(0);
    var forceRef = useState(0);
    var setSnapshot = undefined;
    var snapshot = stateRef.current.snapshot;
    var error = stateRef.current.error;
    var loading = snapshot === undefined && !error;
    var setState = useState({
      snapshot: snapshot,
      error: error,
      loading: loading
    })[1];

    function refresh() {
      counterRef.current = counterRef.current + 1;
      var ticket = counterRef.current;
      Promise.resolve(loader())
        .then(function (next) {
          if (counterRef.current !== ticket) return;
          stateRef.current = { snapshot: next, error: undefined };
          setState({ snapshot: next, error: undefined, loading: false });
        })
        .catch(function (caught) {
          if (counterRef.current !== ticket) return;
          stateRef.current = { snapshot: undefined, error: caught };
          setState({ snapshot: undefined, error: caught, loading: false });
        });
      forceRef[1](counterRef.current);
    }

    useEffect(function () {
      var stopped = false;
      var doc =
        typeof document !== "undefined" ? document : undefined;
      var isVisible = function () {
        return (
          !doc ||
          doc.visibilityState === undefined ||
          doc.visibilityState === "visible"
        );
      };

      function schedule() {
        if (timerRef.current !== null) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
        if (stopped) return;
        if (!isVisible()) return;
        timerRef.current = setTimeout(function () {
          timerRef.current = null;
          if (stopped) return;
          refresh();
          schedule();
        }, intervalMs);
      }

      function handleVisibility() {
        if (isVisible()) {
          refresh();
        }
        schedule();
      }

      refresh();
      schedule();
      if (doc && typeof doc.addEventListener === "function") {
        doc.addEventListener("visibilitychange", handleVisibility);
      }
      return function () {
        stopped = true;
        if (timerRef.current !== null) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
        if (doc && typeof doc.removeEventListener === "function") {
          doc.removeEventListener("visibilitychange", handleVisibility);
        }
      };
      // intervalMs and loader are captured at mount; if the host mounts the
      // component multiple times the effect re-runs intentionally.
    }, []);

    return {
      snapshot: snapshot,
      error: error,
      loading: loading,
      refresh: refresh
    };
  }

  function ScreenGuidance(props) {
    return createElement("aside", {
      className: "daidala-screen-guidance",
      "data-testid": "daidala-screen-guidance-" + props.screen
    },
      createElement("div", null,
        createElement("strong", null, props.title),
        createElement("p", null, props.purpose)
      ),
      createElement("p", { className: "daidala-workflow-meta" }, props.next)
    );
  }

  function SetupAdvicePanel() {
    var resultState = useState(null), result = resultState[0], setResult = resultState[1];
    var busyState = useState(false), busy = busyState[0], setBusy = busyState[1];
    var errorState = useState(""), error = errorState[0], setError = errorState[1];

    function analyze() {
      setBusy(true); setError("");
      requestSetupAnalysis()
        .then(setResult)
        .catch(function (reason) { setError(errorText(reason)); })
        .finally(function () { setBusy(false); });
    }

    var analysis = result && result.analysis ? result.analysis : null;
    var priorities = analysis && Array.isArray(analysis.priorities) ? analysis.priorities : [];
    return createElement("section", { className: "daidala-setup-advice", "data-testid": "daidala-setup-advice" },
      createElement("div", null,
        createElement("h2", null, "Readiness advice"),
        createElement("p", null, "Request a one-off analysis of path-free configuration, workflow, and artifact counts. It is advisory only and does not replace deterministic workflow recommendations.")
      ),
      createElement("button", { type: "button", disabled: busy, onClick: analyze },
        busy ? "Analyzing readiness…" : "Analyze Daidala readiness"
      ),
      !analysis && !error && !busy ? createElement("p", { className: "daidala-workflow-meta" }, "No model analysis has been requested.") : null,
      error ? createElement("p", { role: "status", className: "daidala-banner daidala-banner-warning" }, "Model advice unavailable. Deterministic guidance remains available. " + error) : null,
      analysis ? createElement("div", { className: "daidala-setup-advice-result" },
        createElement("p", null, analysis.summary),
        priorities.length ? createElement("ol", null, priorities.map(function (priority, index) {
          return createElement("li", { key: priority.target + "-" + index },
            createElement("strong", null, priority.title),
            createElement("p", null, priority.advice),
            createElement("button", { type: "button", onClick: function () { openDashboardTarget(priority.target); } },
              "Open " + (ADVICE_TARGETS[priority.target] || { label: "Dashboard" }).label
            )
          );
        })) : null,
        result.model ? createElement("p", { className: "daidala-workflow-meta" }, "Generated by the configured host model: " + result.model.model + ".") : null
      ) : null
    );
  }

  function ConfigurationPanel(props) {
    var tabState = useState(props.section || "packs");
    var tab = tabState[0];
    var setTab = tabState[1];
    var panelRef = useRef(null);

    useEffect(function () {
      if (props.section) setTab(props.section);
    }, [props.section]);

    useEffect(function () {
      if (!props.section || !panelRef.current) return;
      panelRef.current.focus({ preventScroll: true });
      panelRef.current.scrollIntoView({ block: "start" });
    }, [props.section]);

    return createElement(
      "section",
      {
        className: "daidala-config-section",
        "data-testid": "daidala-config",
        "aria-label": "Configuration",
        ref: panelRef,
        tabIndex: -1
      },
      createElement(
        "header",
        { className: "daidala-config-section-header" },
        createElement("p", { className: "daidala-eyebrow" }, "Configuration"),
        createElement("p", { className: "daidala-workflow-meta" },
          "Profile-local settings use server-derived identity and explicit preview confirmation."
        )
      ),
      createElement(
        "div",
        { className: "daidala-config-tabs", role: "tablist", "aria-label": "Configuration" },
        createElement("button", {
          type: "button", role: "tab", "aria-selected": tab === "packs",
          className: tab === "packs" ? "is-selected" : "",
          onClick: function () { setTab("packs"); }
        }, "Packs"),
        createElement("button", {
          type: "button", role: "tab", "aria-selected": tab === "repositories",
          className: tab === "repositories" ? "is-selected" : "",
          onClick: function () { setTab("repositories"); }
        }, "GitHub Repositories"),
        createElement("button", {
          type: "button", role: "tab", "aria-selected": tab === "github-projects",
          className: tab === "github-projects" ? "is-selected" : "",
          onClick: function () { setTab("github-projects"); }
        }, "GitHub Projects"),
        createElement("button", {
          type: "button", role: "tab", "aria-selected": tab === "checkouts",
          className: tab === "checkouts" ? "is-selected" : "",
          onClick: function () { setTab("checkouts"); }
        }, "Checkouts"),
        createElement("button", {
          type: "button", role: "tab", "aria-selected": tab === "constraints",
          className: tab === "constraints" ? "is-selected" : "",
          onClick: function () { setTab("constraints"); }
        }, "Constraints"),
        createElement("button", {
          type: "button", role: "tab", "aria-selected": tab === "verification",
          className: tab === "verification" ? "is-selected" : "",
          onClick: function () { setTab("verification"); }
        }, "Verification"),
        createElement("button", {
          type: "button", role: "tab", "aria-selected": tab === "runbook",
          className: tab === "runbook" ? "is-selected" : "",
          onClick: function () { setTab("runbook"); }
        }, "Runbook")
      ),
      tab === "packs"
        ? createElement(PackBrowser)
        : tab === "repositories"
          ? createElement(RepositoryRegistrationPanel)
          : tab === "github-projects"
            ? createElement(GitHubProjectLinksPanel)
          : tab === "checkouts"
            ? createElement(CheckoutManagerPanel)
            : tab === "constraints"
              ? createElement(ConstraintAuthoringPanel, {
                returnToStart: props.returnToStart,
                onReturnSource: props.onReturnSource
              })
              : tab === "runbook"
                ? createElement(OperatorRunbookPanel, { health: props.health, onResume: props.onResume })
                : createElement(ConfigurationVerificationPanel)
    );
  }

  function configurationStatus(value) {
    if (!value) return "unavailable";
    if (["healthy", "blocked", "not_configured", "unavailable"].indexOf(value.status) >= 0) {
      return value.status;
    }
    if (value.state === "ok") return "healthy";
    return value.state ? "blocked" : "unavailable";
  }

  function InitializationPanel(props) {
    var state = useState(undefined);
    var preview = state[0];
    var setPreview = state[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];

    function refresh() {
      setMessage("");
      return buildInitialization().then(setPreview).catch(function (caught) {
        setPreview(null);
        setMessage(errorText(caught));
      });
    }

    function apply() {
      if (!preview || !confirmed) return;
      applyInitialization(preview.preview_digest).then(function (result) {
        setPreview(result.initialization);
        setConfirmed(false);
        setMessage(result.created ? "Initialization complete." : "Already initialized; no changes made.");
      }).catch(function (caught) { setMessage(errorText(caught)); });
    }

    useEffect(function () { refresh(); }, []);
    return createElement("section", { className: "daidala-config", "data-testid": "daidala-initialization" },
      createElement("button", { type: "button", onClick: props.onBack }, "← Back to verification"),
      createElement("h2", null, "Profile initialization"),
      createElement("p", { className: "daidala-workflow-meta" }, "Preview first. No profile files are created until confirmation."),
      message ? createElement("p", { className: "daidala-banner" }, message) : null,
      preview === undefined ? createElement("p", null, "Loading initialization preview")
        : preview === null ? null
        : createElement(React.Fragment, null,
            createElement("p", null, "Target: " + preview.database),
            createElement("p", null, preview.initialized ? "Schema is initialized." : "Schema is not initialized."),
            createElement("ul", null, preview.effects.map(function (effect) { return createElement("li", { key: effect }, effect); })),
            createElement("code", null, preview.preview_digest),
            createElement("label", null,
              createElement("input", { type: "checkbox", checked: confirmed, onChange: function (event) { setConfirmed(event.target.checked); } }),
              " I confirm this exact initialization preview"
            ),
            createElement("button", { type: "button", disabled: !confirmed, onClick: apply }, "Initialize profile ledger"),
            createElement("button", { type: "button", onClick: refresh }, "Refresh initialization preview")
          )
    );
  }

  function PrerequisiteDiagnosisPanel(props) {
    var resultState = useState(null);
    var result = resultState[0];
    var setResult = resultState[1];

    function diagnose(live) {
      runPrerequisiteDiagnosis(props.projectId, live).then(setResult).catch(function (caught) {
        setResult({ error: errorText(caught) });
      });
    }

    return createElement("section", { className: "daidala-prerequisite-diagnosis" },
      createElement("h4", null, "Prerequisite diagnosis"),
      createElement("button", { type: "button", onClick: function () { diagnose(false); } }, "Run local checks"),
      createElement("button", { type: "button", onClick: function () { diagnose(true); } }, "Run live checks"),
      result && result.error ? createElement("p", { className: "daidala-banner daidala-banner-error" }, result.error) : null,
      result && result.report ? createElement("p", { className: "daidala-workflow-meta" },
        (result.report.live ? "Live" : "Local") + " report · Status: " + result.report.status + " · Exit code: " + result.exit_code + " · Checklist " + result.report.checklist_digest
      ) : null,
      result && result.report && result.report.checks ? createElement("ul", null,
        result.report.checks.map(function (check) {
          return createElement("li", { key: check.check_id },
            check.check_id + " · " + check.status + " · " + check.guide +
            (check.blocker ? " · " + check.blocker : "") +
            (check.evidence && check.evidence.length ? " · " + check.evidence.join("; ") : "")
          );
        })
      ) : null
    );
  }

  function OperatorRunbookPanel(props) {
    var workflowIdState = useState("");
    var workflowId = workflowIdState[0];
    var setWorkflowId = workflowIdState[1];
    var identity = props.health && props.health.identity ? props.health.identity : {};
    var rows = [
      ["Install and enable", "Host-owned CLI", "hermes plugins install forgegod/daidala --enable\nhermes plugins list"],
      ["Register repository", "Profile-local setup", "Follow docs/16-self-improvement-setup.md section 9. The dashboard does not accept repository paths or credentials."],
      ["Initialize", "Configuration verification", "Open initialization preview"],
      ["Diagnose prerequisites", "Configuration verification", "Run local checks or Run live checks"],
      ["Pack dependencies", "Config → Packs", "Validate, inspect, then explicitly install"],
      ["Start and resume", "Workflow supervision", "Select an existing workflow ID to resume read-only polling"],
      ["Approve the exact plan", "Workflow detail", "Inspect the exact plan and confirm approval"],
      ["Review disposition", "Workflow detail", "Preview source-bound review disposition before applying"],
      ["Cancel and recovery", "Workflow detail", "Preview cancellation or use native Hermes Kanban recovery"],
      ["Upgrade", "Host-owned CLI", "hermes plugins update daidala\nhermes daidala doctor --project-manifest /absolute/repository/.daidala/project.yaml\nhermes daidala packs check addyosmani"],
      ["Standalone diagnostics", "Host-owned CLI", "daidala status <workflow-id>"]
    ];
    return createElement("section", { className: "daidala-config", "data-testid": "daidala-operator-runbook" },
      createElement("h2", null, "Operator runbook"),
      createElement("p", { className: "daidala-workflow-meta" }, "Dashboard links are guidance or existing bounded surfaces. Install, enable, upgrade, and gateway lifecycle remain native CLI operations."),
      createElement("p", { className: "daidala-workflow-meta" },
        "Profile: " + (identity.profile || "unavailable") + " · Daidala: " + (identity.daidala_version || "unavailable") + " · Hermes: " + (identity.hermes_version || "unavailable") + " · Supported: " + (identity.supported_hermes_range || "unavailable")
      ),
      createElement("label", null, "Resume existing workflow ID", createElement("input", { value: workflowId, onChange: function (event) { setWorkflowId(event.target.value); } })),
      createElement("button", { type: "button", disabled: !workflowId.trim(), onClick: function () { props.onResume(workflowId.trim()); } }, "Open workflow"),
      createElement("ul", null, rows.map(function (row) {
        return createElement("li", { key: row[0] },
          createElement("strong", null, row[0] + ": "), row[1] + " · ", createElement("code", null, row[2])
        );
      }))
    );
  }

  function ConfigurationVerificationPanel() {
    var state = useState(undefined);
    var inventory = state[0];
    var setInventory = state[1];
    var initializationViewState = useState(false);
    var initializationView = initializationViewState[0];
    var setInitializationView = initializationViewState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];

    function refresh() {
      setError("");
      return buildConfiguration().then(function (value) {
        setInventory(value);
      }).catch(function (caught) {
        setInventory(null);
        setError(errorText(caught));
        throw caught;
      });
    }

    useEffect(function () { refresh().catch(function () {}); }, []);
    if (initializationView) {
      return createElement(InitializationPanel, { onBack: function () { setInitializationView(false); } });
    }
    return createElement("section", { className: "daidala-config", "data-testid": "daidala-configuration-verification" },
      createElement("header", { className: "daidala-config-header" },
        createElement("div", null,
          createElement("h2", null, "Configuration verification"),
          createElement("p", { className: "daidala-workflow-meta" },
            "Read-only persisted configuration and cross-object invariant status."
          )
        ),
        createElement("div", null,
          createElement("button", { type: "button", onClick: function () { refresh().catch(function () {}); } }, "Refresh verification"),
          createElement("button", { type: "button", onClick: function () { setInitializationView(true); } }, "Open initialization preview")
        )
      ),
      error ? createElement("p", { className: "daidala-banner daidala-banner-error" }, error) : null,
      inventory === undefined
        ? createElement("p", { className: "daidala-state daidala-state-loading" }, "Loading configuration verification")
        : inventory === null
          ? null
          : createElement(React.Fragment, null,
              createElement("article", { className: "daidala-github-project-card" },
                createElement("h3", null, "Checkout policy"),
                createElement("p", { className: "daidala-workflow-meta" }, "Root: " + inventory.checkouts.root),
                createElement("p", { className: "daidala-workflow-meta" }, "Mode: " + inventory.checkouts.mode + " · TTL: " + inventory.checkouts.ttl_hours + " hours")
              ),
              inventory.checkouts.mode !== "disabled"
                ? createElement("p", { className: "daidala-banner daidala-banner-warning" },
                    "Manual stale refresh may wipe or back up clean local data; it never runs during admission."
                  )
                : null,
              inventory.registrations.length
                ? inventory.registrations.map(function (registration) {
                    var checkout = registration.checkout || {};
                    var project = registration.github_project || {};
                    var intake = registration.intake || {};
                    var evaluator = registration.evaluator || {};
                    var notification = registration.notification || {};
                    return createElement("article", { className: "daidala-github-project-card", key: registration.project_id },
                      createElement("h3", null, registration.project_id),
                      createElement("p", { className: "daidala-workflow-meta" }, "Derived checkout: " + inventory.checkouts.root + "/" + registration.project_id),
                      createElement("p", { className: "daidala-workflow-meta" }, "Checkout: " + configurationStatus(checkout) + (checkout.state && checkout.state !== "ok" ? " · " + checkout.state : "")),
                      createElement("p", { className: "daidala-workflow-meta" }, "GitHub Project: " + configurationStatus(project) + (project.owner ? " · " + project.owner + " #" + project.project_number : "") + (project.node_id_configured ? " · identity recorded" : "")),
                      createElement("p", { className: "daidala-workflow-meta" }, "GitHub intake: " + configurationStatus(intake) + (intake.reason ? " · " + intake.reason : "")),
                      createElement("p", { className: "daidala-workflow-meta" }, "Evaluator: " + configurationStatus(evaluator) + " · " + (evaluator.backend || "unavailable") + " · " + (evaluator.network || "unavailable")),
                      createElement("p", { className: "daidala-workflow-meta" }, "Notifications: " + configurationStatus(notification) + " · " + (notification.adapter || "unavailable") + " · destination " + (notification.destination_configured ? "configured" : "missing")),
                      createElement(PrerequisiteDiagnosisPanel, { projectId: registration.project_id })
                    );
                  })
                : createElement("p", { className: "daidala-state daidala-state-empty" }, "No registered projects")
            )
    );
  }

  function ConstraintAuthoringPanel(props) {
    var workflowsState = useState(undefined);
    var workflows = workflowsState[0];
    var setWorkflows = workflowsState[1];
    var prerequisitesState = useState(undefined);
    var prerequisites = prerequisitesState[0];
    var setPrerequisites = prerequisitesState[1];
    var sourcesState = useState(undefined);
    var sources = sourcesState[0];
    var setSources = sourcesState[1];
    var selectedWorkflowState = useState(null);
    var selectedWorkflow = selectedWorkflowState[0];
    var setSelectedWorkflow = selectedWorkflowState[1];
    var selectedSourceState = useState(null);
    var selectedSource = selectedSourceState[0];
    var setSelectedSource = selectedSourceState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];

    function refresh() {
      setError("");
      return Promise.all([buildWorkflows(), buildConstraintPrerequisites(), buildConstraintSources()])
        .then(function (values) {
          setWorkflows(values[0] === null ? [] : values[0]);
          setPrerequisites(values[1]);
          setSources(values[2]);
        })
        .catch(function (caught) {
          setError(errorText(caught));
          setWorkflows([]);
          setPrerequisites(null);
          setSources([]);
          throw caught;
        });
    }

    useEffect(function () { refresh().catch(function () {}); }, []);

    function selectWorkflow(workflow) {
      setError("");
      buildWorkflowDetail(workflow.workflow_id).then(function (detail) {
        if (!detail || !detail.workflow) {
          setError("Workflow details are unavailable.");
          return;
        }
        setSelectedWorkflow({ workflow: detail.workflow, constraints: detail.constraints });
      }).catch(function (caught) { setError(errorText(caught)); });
    }

    function selectSource(source) {
      setError("");
      buildConstraintSource(source.name).then(function (detail) {
        setSelectedSource(detail);
      }).catch(function (caught) { setSelectedSource(null); setError(errorText(caught)); });
    }

    return createElement("section", { className: "daidala-config", "data-testid": "daidala-constraint-authoring" },
      createElement("header", { className: "daidala-config-header" },
        createElement("div", null,
          createElement("h2", null, "Constraints"),
          createElement("p", { className: "daidala-workflow-meta" },
            "Reusable sources are read-only. Workflow changes use preview, displayed digest, and explicit confirmation."
          )
        ),
        createElement("button", { type: "button", onClick: function () { refresh().catch(function () {}); } }, "Refresh constraints")
      ),
      error ? createElement("p", { className: "daidala-banner daidala-banner-error" }, error) : null,
      workflows === undefined || sources === undefined || prerequisites === undefined
        ? createElement("p", { className: "daidala-state daidala-state-loading" }, "Loading constraint inventory")
        : createElement(React.Fragment, null,
            createElement("section", { className: "daidala-constraint-source-browser" },
              createElement("h3", null, "Reusable policy sources"),
              sources.length
                ? createElement("div", { className: "daidala-config-actions" }, sources.map(function (source) {
                    return createElement("button", { key: source.name, type: "button", onClick: function () { selectSource(source); } }, source.name);
                  }))
                : createElement("p", { className: "daidala-workflow-meta" }, "No reusable policy sources are installed."),
              selectedSource ? selectedSource.available
                ? createElement("article", { className: "daidala-skill-document", "data-testid": "daidala-constraint-source" },
                    createElement("h4", null, selectedSource.source.name + " · reusable policy source"),
                    createElement("p", { className: "daidala-skill-digest" }, "Verified digest " + selectedSource.source.digest),
                    createElement("pre", null, selectedSource.skill_markdown),
                    props.returnToStart && props.onReturnSource
                      ? createElement("button", { type: "button", onClick: function () { props.onReturnSource(selectedSource.source); } }, "Use selected source in Start draft")
                      : null
                  )
                : createElement("p", { className: "daidala-banner daidala-banner-error" }, selectedSource.reason || "Selected source is unavailable.")
                : null
            ),
            createElement("section", { className: "daidala-constraint-workflow-selector" },
              createElement("h3", null, "Workflow policy maintenance"),
              workflows.length
                ? workflows.map(function (workflow) {
                    var isNew = !workflow.current_constraints_digest;
                    return createElement("article", { className: "daidala-github-project-card", key: workflow.workflow_id },
                      createElement("h4", null, workflow.workflow_id),
                      createElement("p", { className: "daidala-workflow-meta" },
                        isNew ? "No current constraint identity." : "Current digest " + workflow.current_constraints_digest
                      ),
                      createElement("button", { type: "button", onClick: function () { selectWorkflow(workflow); } }, isNew ? "New workflow constraints" : "Edit constraints")
                    );
                  })
                : createElement("p", { className: "daidala-workflow-meta" }, "No existing workflows. Start workflow owns authoring before creation."),
              selectedWorkflow
                ? createElement(ConstraintEditor, {
                    key: selectedWorkflow.workflow.workflow_id + ":" + (selectedWorkflow.workflow.current_constraints_digest || "new"),
                    workflow: selectedWorkflow.workflow,
                    constraints: selectedWorkflow.constraints,
                    source: selectedSource,
                    template: prerequisites.constraint_template,
                    schemaLimits: prerequisites.schema_limits,
                    onApplied: function () {
                      setSelectedWorkflow(null);
                      refresh().catch(function () {});
                    }
                  })
                : null
            )
          )
    );
  }

  function CheckoutManagerPanel() {
    var state = useState(undefined);
    var inventory = state[0];
    var setInventory = state[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];
    var pendingState = useState(null);
    var pending = pendingState[0];
    var setPending = pendingState[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var policyModeState = useState("wipe-if-clean");
    var policyMode = policyModeState[0];
    var setPolicyMode = policyModeState[1];
    var ttlState = useState("24");
    var ttlHours = ttlState[0];
    var setTtlHours = ttlState[1];

    function refresh() {
      setError("");
      return fetchJson(API_BASE + "/checkouts")
        .then(function (value) { setInventory(value); })
        .catch(function (caught) {
          setInventory(null);
          setError(errorText(caught));
          throw caught;
        });
    }

    function previewCheckoutAction(projectId, kind) {
      setBusy(true);
      setError("");
      return postJson(
        API_BASE + "/checkouts/" + encodeURIComponent(projectId) + "/" + kind + "/preview",
        {}
      ).then(function (preview) {
        setPending({ kind: kind, project_id: projectId, preview: preview });
        setConfirmed(false);
      }).catch(function (caught) {
        setError(errorText(caught));
        throw caught;
      }).finally(function () { setBusy(false); });
    }

    function previewBackupPrune(name) {
      setBusy(true);
      setError("");
      return postJson(API_BASE + "/checkouts/_backups/prune/preview", { filenames: [name] })
        .then(function (preview) {
          setPending({ kind: "backup-prune", filenames: [name], preview: preview });
          setConfirmed(false);
        }).catch(function (caught) {
          setError(errorText(caught));
          throw caught;
        }).finally(function () { setBusy(false); });
    }

    function previewPolicy() {
      var hours = Number(ttlHours);
      setBusy(true);
      setError("");
      return postJson(API_BASE + "/checkouts/policy/preview", {
        mode: policyMode,
        ttl_hours: hours
      }).then(function (preview) {
        setPending({
          kind: "policy",
          mode: policyMode,
          ttl_hours: hours,
          preview: preview
        });
        setConfirmed(false);
      }).catch(function (caught) {
        setError(errorText(caught));
        throw caught;
      }).finally(function () { setBusy(false); });
    }

    function applyPending() {
      if (!pending || !confirmed) {
        return;
      }
      var request;
      if (pending.kind === "backup-prune") {
        request = postJson(API_BASE + "/checkouts/_backups/prune", {
          filenames: pending.filenames,
          preview_digest: pending.preview.preview_digest,
          confirm: true
        });
      } else if (pending.kind === "policy") {
        request = putJson(API_BASE + "/checkouts/policy", {
          mode: pending.mode,
          ttl_hours: pending.ttl_hours,
          preview_digest: pending.preview.preview_digest,
          confirm: true
        });
      } else {
        request = postJson(
          API_BASE + "/checkouts/" + encodeURIComponent(pending.project_id) + "/" + pending.kind,
          { preview_digest: pending.preview.preview_digest, confirm: true }
        );
      }
      setBusy(true);
      setError("");
      return request.then(function () {
        setPending(null);
        setConfirmed(false);
        return refresh();
      }).catch(function (caught) {
        setError(errorText(caught));
        throw caught;
      }).finally(function () { setBusy(false); });
    }

    useEffect(function () { refresh().catch(function () {}); }, []);
    return createElement(
      "section",
      { className: "daidala-config", "data-testid": "daidala-checkouts" },
      createElement(
        "header",
        { className: "daidala-config-header" },
        createElement("div", null,
          createElement("h2", null, "Checkouts"),
          createElement("p", { className: "daidala-workflow-meta" },
            "Server-derived inventory. Every lifecycle change requires an exact preview and confirmation."
          )
        ),
        createElement("button", {
          type: "button", disabled: busy,
          onClick: function () { refresh().catch(function () {}); }
        }, "Refresh status")
      ),
      inventory === undefined
        ? createElement("p", { className: "daidala-state daidala-state-loading" }, "Loading checkouts")
        : error
          ? createElement("p", { className: "daidala-banner daidala-banner-error" }, error)
          : createElement(
              "div",
              { className: "daidala-github-project-links-grid" },
              createElement("p", { className: "daidala-workflow-meta" },
                "Policy: " + inventory.policy.mode + " · TTL: " + String(inventory.policy.ttl_hours) + " hours"
              ),
              createElement("div", { className: "daidala-config-actions" },
                createElement("label", null, "Checkout policy ",
                  createElement("select", {
                    value: policyMode,
                    onChange: function (event) {
                      var nextMode = event.target.value;
                      setPolicyMode(nextMode);
                      if (nextMode === "disabled") {
                        setTtlHours("0");
                      } else if (ttlHours === "0") {
                        setTtlHours("24");
                      }
                    }
                  },
                  createElement("option", { value: "disabled" }, "disabled"),
                  createElement("option", { value: "wipe-if-clean" }, "wipe-if-clean"),
                  createElement("option", { value: "backup-then-wipe" }, "backup-then-wipe"))
                ),
                createElement("label", null, "TTL hours ",
                  createElement("input", {
                    type: "number", min: "0", max: "8760", value: ttlHours,
                    onChange: function (event) { setTtlHours(event.target.value); }
                  })
                ),
                createElement("button", {
                  type: "button", disabled: busy,
                  onClick: function () { previewPolicy().catch(function () {}); }
                }, "Preview policy change")
              ),
              inventory.checkouts.map(function (checkout) {
                return createElement("article", { className: "daidala-github-project-card", key: checkout.project_id },
                  createElement("h3", null, checkout.project_id),
                  createElement("p", { className: "daidala-workflow-meta" },
                    "Status: " + checkout.state + " · tracked " + String(checkout.tracked_count) +
                    " · untracked " + String(checkout.untracked_count) +
                    " · ignored " + String(checkout.ignored_count)
                  ),
                  checkout.recovery_required
                    ? createElement("p", { className: "daidala-banner daidala-banner-error" },
                        "A prior operation needs manual recovery before another action.")
                    : createElement("div", { className: "daidala-config-actions" },
                        createElement("button", {
                          type: "button", disabled: busy,
                          onClick: function () {
                            previewCheckoutAction(checkout.project_id, "refresh").catch(function () {});
                          }
                        }, "Preview refresh"),
                        checkout.state === "unowned"
                          ? createElement("button", {
                              type: "button", disabled: busy,
                              onClick: function () {
                                previewCheckoutAction(checkout.project_id, "adopt").catch(function () {});
                              }
                            }, "Preview adoption")
                          : null
                      )
                );
              }),
              Array.isArray(inventory.backups) && inventory.backups.length
                ? createElement("article", { className: "daidala-github-project-card" },
                    createElement("h3", null, "Backups"),
                    inventory.backups.map(function (name) {
                      return createElement("div", { className: "daidala-config-actions", key: name },
                        createElement("span", { className: "daidala-workflow-meta" }, name),
                        createElement("button", {
                          type: "button", disabled: busy,
                          onClick: function () { previewBackupPrune(name).catch(function () {}); }
                        }, "Preview prune")
                      );
                    })
                  )
                : null,
              pending
                ? createElement("article", {
                    className: "daidala-github-project-card",
                    "data-testid": "daidala-checkout-preview"
                  },
                  createElement("h3", null, "Checkout action preview"),
                  createElement("p", { className: "daidala-workflow-meta" },
                    "Action: " + pending.kind + " · server decision: " +
                    (pending.preview.action || pending.kind)
                  ),
                  createElement("label", null,
                    createElement("input", {
                      type: "checkbox", checked: confirmed,
                      onChange: function (event) { setConfirmed(event.target.checked); }
                    }),
                    " I confirm applying this exact checkout preview"
                  ),
                  createElement("button", {
                    type: "button", disabled: !confirmed || busy,
                    onClick: function () { applyPending().catch(function () {}); }
                  }, busy ? "Applying…" : "Apply confirmed checkout action")
                )
                : null
            )
    );
  }

  var DEFAULTS_FIELD_SPECS = {
    "credentials.intake.alias": {
      label: "Intake alias",
      placeholder: "github-read-issues",
      help: "Logical name for the already-configured read-only GitHub access used to list and claim issues. Lowercase slug such as github-read-issues. Must differ from the findings alias. This is a label, not the GitHub token."
    },
    "credentials.intake.environment_variable": {
      label: "Intake environment variable",
      placeholder: "EXAMPLE_GITHUB_INTAKE_TOKEN",
      help: "Name of the process environment variable that already holds the intake GitHub token, such as EXAMPLE_GITHUB_INTAKE_TOKEN. Uppercase letters, digits, and underscores only. Never GH_TOKEN, and never paste the GitHub token itself. Use a classic personal access token, not a fine-grained token. Mandatory classic scopes are read:project and read:org. Leave repo, public_repo, project write, workflow, package, administration, and deletion unselected. Fine-grained tokens cannot access user-owned GitHub Projects."
    },
    "credentials.findings.alias": {
      label: "Findings alias",
      placeholder: "github-write-issues",
      help: "Logical name for the already-configured write GitHub access used to open or update finding issues. Use a different lowercase slug such as github-write-issues so read and write stay separate."
    },
    "credentials.findings.environment_variable": {
      label: "Findings environment variable",
      placeholder: "EXAMPLE_GITHUB_FINDINGS_TOKEN",
      help: "Name of the process environment variable that already holds the findings GitHub token. It must differ from the intake variable. Same uppercase name rules; never GH_TOKEN or the GitHub token value. Use a fine-grained personal access token, the current GitHub token type, restricted to the target repository. Mandatory repository permissions are Metadata read and Issues read and write. Leave Contents, Administration, Pull requests, Actions, Workflows, Deployments, and other permissions at No access."
    },
    "approval.maintainers": {
      label: "Maintainers",
      placeholder: "example-operator",
      help: "Allowlist copied onto every new registration from this profile. Only these GitHub usernames may mark an issue ready and admit a cycle. The same list authorizes issue claim comments and must match the authorized maintainer in notification prerequisite evidence. This is not dashboard plan approval. Enter the login in the profile URL, such as example-operator for github.com/example-operator. Comma-separated, 1 to 32, no duplicates. Do not use an email address, display name, Hermes profile name, or Git author name."
    },
    "notifications.target": {
      label: "Notification target",
      placeholder: "attended-example",
      help: "Identity label for the attended destination, such as attended-example. Lowercase slug. It is not part of the message content. Daidala stamps this name on every notification receipt and requires receipts to match this registration at admission, completion, and cancellation; a receipt claiming a different target blocks the transition. It is the integrity binding of the notification evidence, not a salutation. Do not change it casually because recorded receipts are bound to the registered slug."
    },
    "notifications.destination": {
      label: "Notification destination",
      placeholder: "telegram:-1000000000000:1",
      help: "Where Hermes sends attended reviews. Must be an explicit non-home target such as telegram:<chat-id> or telegram:<chat-id>:<thread-id>. Do not use home."
    },
    "limits.active_cycles": {
      label: "Active cycles",
      placeholder: "1",
      help: "Declared cycle concurrency copied onto every new registration. v1 requires exactly 1."
    },
    "limits.goal_turns": {
      label: "Goal turns",
      placeholder: "12",
      help: "Declared maximum planning and implementation turns per cycle, copied onto every new registration. Integer from 1 to 100. 12 is the recommended start."
    },
    "limits.delegated_workers": {
      label: "Delegated workers",
      placeholder: "3",
      help: "Declared maximum extra workers one cycle may spawn, copied onto every new registration. Integer from 0 to 9. 3 is the recommended start."
    },
    "limits.research_query_batches": {
      label: "Research query batches",
      placeholder: "3",
      help: "Declared maximum research batches one cycle may run, copied onto every new registration. Integer from 0 to 10. 3 is the recommended start."
    },
    "limits.extracted_sources": {
      label: "Extracted sources",
      placeholder: "3",
      help: "Declared maximum extracted source documents one cycle may keep, copied onto every new registration. Integer from 0 to 20. 3 is the recommended start."
    },
    "limits.wall_clock_seconds": {
      label: "Wall-clock seconds",
      placeholder: "3600",
      help: "Declared maximum elapsed seconds for one cycle, copied onto every new registration. Integer from 60 to 86400. 3600 is one hour."
    }
  };

  function emptyDefaultsDraft() {
    return {
      schema: "daidala.repository-registration-defaults/v1",
      credentials: {
        intake: { alias: "", resolver: "environment", environment_variable: "" },
        findings: { alias: "", resolver: "environment", environment_variable: "" }
      },
      approval: { maintainers: "" },
      notifications: { adapter: "hermes-gateway", target: "", destination: "" },
      evaluator: { backend: "restricted-container", network: "denied-by-default" },
      limits: {
        active_cycles: "1",
        goal_turns: "12",
        delegated_workers: "3",
        research_query_batches: "3",
        extracted_sources: "3",
        wall_clock_seconds: "3600"
      }
    };
  }

  function defaultsDraftFromPreview(preview) {
    var source = preview && preview.defaults ? preview.defaults : emptyDefaultsDraft();
    var credentials = source.credentials || {};
    var intake = credentials.intake || {};
    var findings = credentials.findings || {};
    var approval = source.approval || {};
    var notifications = source.notifications || {};
    var limits = source.limits || {};
    return {
      schema: "daidala.repository-registration-defaults/v1",
      credentials: {
        intake: {
          alias: intake.alias || "",
          resolver: "environment",
          environment_variable: intake.environment_variable || ""
        },
        findings: {
          alias: findings.alias || "",
          resolver: "environment",
          environment_variable: findings.environment_variable || ""
        }
      },
      approval: {
        maintainers: Array.isArray(approval.maintainers)
          ? approval.maintainers.join(", ")
          : (approval.maintainers || "")
      },
      notifications: {
        adapter: "hermes-gateway",
        target: notifications.target || "",
        destination: notifications.destination || ""
      },
      evaluator: { backend: "restricted-container", network: "denied-by-default" },
      limits: {
        active_cycles: String(limits.active_cycles == null ? 1 : limits.active_cycles),
        goal_turns: String(limits.goal_turns == null ? 12 : limits.goal_turns),
        delegated_workers: String(limits.delegated_workers == null ? 3 : limits.delegated_workers),
        research_query_batches: String(limits.research_query_batches == null ? 3 : limits.research_query_batches),
        extracted_sources: String(limits.extracted_sources == null ? 3 : limits.extracted_sources),
        wall_clock_seconds: String(limits.wall_clock_seconds == null ? 3600 : limits.wall_clock_seconds)
      }
    };
  }

  function defaultsPayloadFromDraft(draft) {
    var maintainers = String(draft.approval.maintainers || "").split(",").map(function (row) {
      return row.trim();
    }).filter(Boolean);
    return {
      schema: "daidala.repository-registration-defaults/v1",
      credentials: {
        intake: {
          alias: draft.credentials.intake.alias.trim(),
          resolver: "environment",
          environment_variable: draft.credentials.intake.environment_variable.trim()
        },
        findings: {
          alias: draft.credentials.findings.alias.trim(),
          resolver: "environment",
          environment_variable: draft.credentials.findings.environment_variable.trim()
        }
      },
      approval: { maintainers: maintainers },
      notifications: {
        adapter: "hermes-gateway",
        target: draft.notifications.target.trim(),
        destination: draft.notifications.destination.trim()
      },
      evaluator: { backend: "restricted-container", network: "denied-by-default" },
      limits: {
        active_cycles: Number(draft.limits.active_cycles),
        goal_turns: Number(draft.limits.goal_turns),
        delegated_workers: Number(draft.limits.delegated_workers),
        research_query_batches: Number(draft.limits.research_query_batches),
        extracted_sources: Number(draft.limits.extracted_sources),
        wall_clock_seconds: Number(draft.limits.wall_clock_seconds)
      }
    };
  }

  function repositoryInspectionMessage(result) {
    if (!result || typeof result !== "object") {
      return "Repository inspection unavailable.";
    }
    var classification = result.classification || result.status || "";
    var reason = typeof result.reason === "string" && result.reason
      ? result.reason
      : "Repository inspection is blocked.";
    var repository = typeof result.repository === "string" && result.repository
      ? result.repository + ": "
      : "";
    if (classification === "needs-bootstrap") {
      return repository + reason +
        " Bootstrap Daidala policy on a non-default branch, merge it to the default branch, then inspect again.";
    }
    if (classification === "already-registered") {
      return repository + reason;
    }
    if (classification === "blocked") {
      return repository + reason;
    }
    return repository + reason;
  }

  function RepositoryRegistrationPanel() {
    var inventoryState = useState(undefined);
    var inventory = inventoryState[0];
    var setInventory = inventoryState[1];
    var draftsState = useState({});
    var drafts = draftsState[0];
    var setDrafts = draftsState[1];
    var activeState = useState(null);
    var active = activeState[0];
    var setActive = activeState[1];
    var previewState = useState(null);
    var preview = previewState[0];
    var setPreview = previewState[1];
    var bootstrapPreviewState = useState(null);
    var bootstrapPreview = bootstrapPreviewState[0];
    var setBootstrapPreview = bootstrapPreviewState[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];
    var defaultsWizardState = useState(null);
    var defaultsWizard = defaultsWizardState[0];
    var setDefaultsWizard = defaultsWizardState[1];
    var defaultsDraftState = useState(emptyDefaultsDraft());
    var defaultsDraft = defaultsDraftState[0];
    var setDefaultsDraft = defaultsDraftState[1];
    var defaultsPreviewState = useState(null);
    var defaultsPreview = defaultsPreviewState[0];
    var setDefaultsPreview = defaultsPreviewState[1];
    var defaultsConfirmedState = useState(false);
    var defaultsConfirmed = defaultsConfirmedState[0];
    var setDefaultsConfirmed = defaultsConfirmedState[1];

    function draftKey(profileName, field) {
      return profileName + "\0" + field;
    }

    function defaultUrl(registration, pending) {
      if (registration && registration.repository_canonical) {
        return "github.com/" + registration.repository_canonical;
      }
      if (pending && pending.repository_canonical) {
        return "github.com/" + pending.repository_canonical;
      }
      return "";
    }

    function fieldUrl(profileName, field, registration, pending) {
      var key = draftKey(profileName, field);
      return Object.prototype.hasOwnProperty.call(drafts, key)
        ? drafts[key]
        : defaultUrl(registration, pending);
    }

    function setFieldUrl(profileName, field, value) {
      var next = {};
      Object.keys(drafts).forEach(function (existing) { next[existing] = drafts[existing]; });
      next[draftKey(profileName, field)] = value;
      setDrafts(next);
      setPreview(null);
      setBootstrapPreview(null);
      setConfirmed(false);
    }

    function refreshInventory() {
      setMessage("");
      return buildRepositoryRegistrationInventory().then(setInventory).catch(function (caught) {
        setInventory([]);
        setMessage("Hermes profile inventory unavailable: " + errorText(caught));
      });
    }

    useEffect(function () { refreshInventory().catch(function () {}); }, []);

    function pendingBootstraps(profileName) {
      var profiles = Array.isArray(inventory) ? inventory : [];
      var profile = profiles.filter(function (row) {
        return row && row.controller_profile === profileName;
      })[0];
      return profile && Array.isArray(profile.pending_bootstraps) ? profile.pending_bootstraps : [];
    }

    function pendingForUrl(profileName, githubUrl) {
      var normalized = String(githubUrl || "").replace(/^https?:\/\//, "").replace(/^github\.com\//, "");
      return pendingBootstraps(profileName).filter(function (row) {
        return row && row.repository_canonical === normalized;
      })[0] || null;
    }

    function openDefaultsWizard(profileName, seed) {
      setDefaultsWizard(profileName);
      setDefaultsPreview(null);
      setDefaultsConfirmed(false);
      setBusy(true);
      setMessage("");
      var request = seed ? previewRegistrationDefaults(profileName, { seed: true }) : previewRegistrationDefaults(profileName);
      return request.then(function (preview) {
        setDefaultsPreview(preview);
        setDefaultsDraft(defaultsDraftFromPreview(preview));
        if (!preview.valid && preview.reason) setMessage(preview.reason);
      }).catch(function (caught) {
        setMessage("Registration defaults preview unavailable: " + errorText(caught));
      }).finally(function () { setBusy(false); });
    }

    function validateDefaultsDraft(profileName) {
      setBusy(true);
      setMessage("");
      setDefaultsConfirmed(false);
      return previewRegistrationDefaults(profileName, { defaults: defaultsPayloadFromDraft(defaultsDraft) }).then(function (preview) {
        setDefaultsPreview(preview);
        if (preview.valid) {
          setMessage("Registration defaults are valid. Confirm to save.");
        } else {
          setMessage(preview.reason || "Registration defaults are invalid.");
        }
      }).catch(function (caught) {
        setMessage("Registration defaults preview unavailable: " + errorText(caught));
      }).finally(function () { setBusy(false); });
    }

    function applyDefaultsWizard(profileName) {
      if (!defaultsPreview || !defaultsPreview.valid || !defaultsConfirmed) return;
      setBusy(true);
      setMessage("");
      var options = defaultsPreview.source === "seed"
        ? { seed: true }
        : { defaults: defaultsPayloadFromDraft(defaultsDraft) };
      return applyRegistrationDefaults(profileName, defaultsPreview.digest, options).then(function () {
        setDefaultsConfirmed(false);
        setDefaultsWizard(null);
        setMessage("Registration defaults saved. Inspect the repository again.");
        refreshInventory().catch(function () {});
      }).catch(function (caught) {
        setMessage("Registration defaults were not saved: " + errorText(caught));
      }).finally(function () { setBusy(false); });
    }

    function updateDefaultsDraft(path, value) {
      var next = JSON.parse(JSON.stringify(defaultsDraft));
      var cursor = next;
      var parts = path.split(".");
      parts.slice(0, -1).forEach(function (part) { cursor = cursor[part]; });
      cursor[parts[parts.length - 1]] = value;
      setDefaultsDraft(next);
      setDefaultsPreview(null);
      setDefaultsConfirmed(false);
    }

    function inspect(profileName, field, registration) {
      var githubUrl = fieldUrl(profileName, field, registration).trim();
      if (!githubUrl || !profileName) return;
      setActive({ profile: profileName, field: field });
      setBusy(true); setMessage(""); setPreview(null); setBootstrapPreview(null); setConfirmed(false);
      previewRepositoryRegistration(githubUrl, profileName).then(function (result) {
        if (result && result.classification === "needs-bootstrap") {
          setMessage(repositoryInspectionMessage(result));
          if (pendingForUrl(profileName, githubUrl)) {
            return;
          }
          return previewRepositoryBootstrap(githubUrl, profileName).then(function (bootstrap) {
            setBootstrapPreview(bootstrap);
          });
        }
        if (!result || result.valid === false || result.classification === "already-registered" || result.classification === "blocked") {
          setPreview(null);
          setMessage(repositoryInspectionMessage(result));
          if (result && String(result.reason || "").indexOf("registration defaults") >= 0) {
            openDefaultsWizard(profileName).catch(function () {});
          }
          return;
        }
        setPreview(result);
      }).catch(function (caught) {
        setMessage("Repository inspection unavailable: " + errorText(caught));
      }).finally(function () { setBusy(false); });
    }

    function apply() {
      if (!preview || !confirmed || !active) return;
      var githubUrl = fieldUrl(active.profile, active.field).trim();
      setBusy(true); setMessage("");
      applyRepositoryRegistration(githubUrl, preview.controller_profile, preview.preview_digest, preview.board).then(function (result) {
        setPreview(result); setConfirmed(false);
        setMessage("Repository registered. Refresh Configuration verification before starting a workflow.");
        refreshInventory().catch(function () {});
      }).catch(function (caught) {
        setMessage("Repository was not registered: " + errorText(caught));
      }).finally(function () { setBusy(false); });
    }

    function applyBootstrap() {
      if (!bootstrapPreview || !confirmed || !active) return;
      var githubUrl = fieldUrl(active.profile, active.field).trim();
      setBusy(true); setMessage("");
      applyRepositoryBootstrap(githubUrl, bootstrapPreview.controller_profile, bootstrapPreview.preview_digest).then(function (result) {
        setBootstrapPreview(result); setConfirmed(false);
        setMessage(
          "Default policy pull request opened on the inspected repository. Merge it, then inspect and register."
        );
        refreshInventory().catch(function () {});
      }).catch(function (caught) {
        setMessage("Repository bootstrap was not applied: " + errorText(caught));
      }).finally(function () { setBusy(false); });
    }

    function isActive(profileName, field) {
      return active && active.profile === profileName && active.field === field;
    }

    function renderPendingLink(profileName, githubUrl) {
      var pending = pendingForUrl(profileName, githubUrl);
      if (!pending || !pending.open_url) return null;
      return createElement("p", { className: "daidala-workflow-meta" },
        "Default policy branch is waiting for merge. ",
        createElement("button", {
          type: "button",
          onClick: function () {
            window.open(pending.open_url, "_blank", "noopener,noreferrer");
          }
        }, pending.pull_request ? "Open pull request" : "Open a pull request")
      );
    }

    function renderInspectResult(profileName, field) {
      if (!isActive(profileName, field)) return null;
      var readiness = preview && preview.readiness ? preview.readiness : {};
      var writes = preview && preview.writes ? preview.writes : {};
      var nodes = [];
      if (message) {
        nodes.push(createElement("p", { key: "message", role: "status", className: "daidala-banner" }, message));
      }
      if (bootstrapPreview) {
        nodes.push(createElement("section", { key: "bootstrap", className: "daidala-github-link-preview" },
          createElement("h3", null, "Bootstrap preview"),
          createElement("p", null, "Repository: " + bootstrapPreview.repository + " · Project: " + bootstrapPreview.project_id),
          createElement("p", null, "Profile: " + bootstrapPreview.controller_profile),
          createElement("p", null, "Target branch: " + bootstrapPreview.target_branch + " from " + bootstrapPreview.default_branch),
          createElement("p", null, "Files: " + ((bootstrapPreview.files || []).map(function (file) { return file.path; }).join(", ") || "none")),
          createElement("p", null, "Manifest digest: " + bootstrapPreview.manifest_digest),
          createElement("p", { className: "daidala-workflow-meta" }, bootstrapPreview.next_step || "Open the compare/pull-request link, merge on GitHub, then register."),
          createElement("p", { className: "daidala-workflow-meta" }, "Bootstrap does not register the repository, touch the default branch, or store a token. It opens a pull request on the inspected repository."),
          bootstrapPreview.links ? createElement("ul", { className: "daidala-list" },
            bootstrapPreview.links.branch ? createElement("li", { key: "branch" },
              createElement("a", { href: bootstrapPreview.links.branch, target: "_blank", rel: "noreferrer" }, "Open bootstrap branch")
            ) : null,
            bootstrapPreview.links.daidala_tree ? createElement("li", { key: "tree" },
              createElement("a", { href: bootstrapPreview.links.daidala_tree, target: "_blank", rel: "noreferrer" }, "Open .daidala on bootstrap branch")
            ) : null,
            bootstrapPreview.applied && (bootstrapPreview.links.pull_request || bootstrapPreview.links.compare_pull_request) ? createElement("li", { key: "pr" },
              createElement("button", {
                type: "button",
                onClick: function () {
                  window.open(
                    bootstrapPreview.links.pull_request || bootstrapPreview.links.compare_pull_request,
                    "_blank",
                    "noopener,noreferrer"
                  );
                }
              }, bootstrapPreview.links.pull_request ? "Open pull request" : "Open a pull request")
            ) : null
          ) : null,
          createElement("code", null, bootstrapPreview.preview_digest),
          createElement("label", { className: "daidala-pack-confirm" },
            createElement("input", { type: "checkbox", checked: confirmed, onChange: function (event) { setConfirmed(event.target.checked); } }),
            " I confirm publishing bootstrap policy on branch " + bootstrapPreview.target_branch
          )
        ));
      }
      if (preview) {
        nodes.push(createElement("section", { key: "preview", className: "daidala-github-link-preview" },
          createElement("h3", null, "Registration preview"),
          createElement("p", null, "Repository: " + preview.repository + " · Project: " + preview.project_id),
          createElement("p", null, "Profile: " + preview.controller_profile),
          createElement("p", null, "Board: " + preview.board + " (" + preview.board_action + ")"),
          createElement("p", null, "Manifest digest: " + preview.manifest_digest),
          createElement("p", null, "Release policy: commit " + (preview.release.allow_commit ? "allowed" : "denied") + ", push " + (preview.release.allow_push ? "allowed" : "denied") + ", publish " + (preview.release.allow_publish ? "allowed" : "denied")),
          createElement("p", null, "Readiness: board " + (readiness.board_selected ? "selected" : "missing") + ", attended target " + (readiness.attended_target_configured ? "configured" : "missing") + ", credential " + (readiness.credential_available ? "available" : "not available")),
          createElement("p", null, "This preview creates " + (writes.record_count || 0) + " non-secret profile-local records."),
          createElement("p", { className: "daidala-workflow-meta" }, "This action does not commit, push, create a GitHub Project, or store a token."),
          createElement("code", null, preview.preview_digest),
          createElement("label", { className: "daidala-pack-confirm" },
            createElement("input", { type: "checkbox", checked: confirmed, onChange: function (event) { setConfirmed(event.target.checked); } }),
            " I confirm registering this exact repository"
          ),
          createElement("button", { type: "button", disabled: busy || !confirmed, onClick: apply }, "Register repository")
        ));
      }
      return nodes.length ? nodes : null;
    }

    function renderDefaultsField(path) {
      var spec = DEFAULTS_FIELD_SPECS[path];
      var cursor = defaultsDraft;
      path.split(".").forEach(function (part) { cursor = cursor ? cursor[part] : ""; });
      var helpId = "daidala-defaults-help-" + path.replace(/\./g, "-");
      return createElement("label", { className: "daidala-wizard-field", key: path },
        createElement("span", null, spec.label),
        createElement("small", { id: helpId, className: "daidala-field-help" }, spec.help),
        createElement("input", {
          value: cursor == null ? "" : String(cursor),
          placeholder: spec.placeholder,
          "aria-label": spec.label,
          "aria-describedby": helpId,
          onChange: function (event) { updateDefaultsDraft(path, event.target.value); }
        })
      );
    }

    function renderDefaultsGroup(title, paths) {
      return createElement("fieldset", { className: "daidala-defaults-group", key: title },
        createElement("legend", null, title),
        paths.map(renderDefaultsField)
      );
    }

    function renderDefaultsWizard(profileName, defaultsStatus) {
      var status = defaultsStatus && defaultsStatus.status ? defaultsStatus.status : "missing";
      var open = defaultsWizard === profileName;
      return createElement("section", {
        key: profileName + ":defaults",
        className: "daidala-github-registration-context",
        "data-testid": "daidala-registration-defaults"
      },
        createElement("p", { className: "daidala-workflow-meta" },
          status === "valid" ? "Registration defaults are configured."
            : status === "invalid" ? "Registration defaults are invalid."
              : "Registration defaults are not configured for this profile."
        ),
        createElement("div", { className: "daidala-config-actions" },
          createElement("button", {
            type: "button",
            disabled: busy,
            onClick: function () { openDefaultsWizard(profileName, false).catch(function () {}); }
          }, status === "valid" ? "Edit registration defaults" : "Configure registration defaults"),
          defaultsStatus && defaultsStatus.seed_available
            ? createElement("button", {
                type: "button",
                disabled: busy,
                onClick: function () { openDefaultsWizard(profileName, true).catch(function () {}); }
              }, "Seed from existing registration")
            : null
        ),
        open ? createElement("form", {
          className: "daidala-github-link-preview",
          onSubmit: function (event) { event.preventDefault(); }
        },
          createElement("h3", null, "Registration defaults"),
          createElement("p", { className: "daidala-workflow-meta" },
            "These values are profile defaults saved in $HERMES_HOME/repository-registration-defaults.yaml (normally ~/.hermes/profiles/<profile>/repository-registration-defaults.yaml). Reopen this profile's Edit registration defaults form to change them later."
          ),
          createElement("p", { className: "daidala-workflow-meta" },
            "Every new repository registration receives a one-time copy in $HERMES_HOME/projects/<project-id>/registration.yaml and $HERMES_HOME/projects/<project-id>/credential-bindings.yaml; changing the defaults does not update an existing registration. Here, <project-id> is Daidala's stable repository identifier declared in the repository's committed .daidala/project.yaml; it is not a GitHub Project."
          ),
          createElement("p", { className: "daidala-workflow-meta" },
            "For a repository without that policy, Daidala derives the project ID from its GitHub owner and repository name during the Apply default policy preview, then writes it only to the confirmed bootstrap branch. It becomes effective after a maintainer reviews and merges that pull request. When a maintainer authors .daidala/project.yaml manually, they choose a valid project ID instead. Treat the committed ID as stable: it is not a routine setting to maintain, and changing it after registration has no supported migration path."
          ),
          createElement("p", { className: "daidala-workflow-meta" },
            "A GitHub Project is optional: registration neither requires nor creates one, and a separately configured link is only presentation/intake metadata. Registration-specific values are immutable, so there is no per-repository edit control."
          ),
          createElement("p", { className: "daidala-workflow-meta" },
            "Enter aliases and environment-variable names only. GitHub token values are read from the selected Hermes profile's process environment; define them in the file reported by hermes -p <profile> config env-path (normally ~/.hermes/profiles/<profile>/.env) and restart the relevant Hermes process after changing that file."
          ),
          renderDefaultsGroup("Configured GitHub access rights", [
            "credentials.intake.alias",
            "credentials.intake.environment_variable",
            "credentials.findings.alias",
            "credentials.findings.environment_variable"
          ]),
          renderDefaultsGroup("Approval", ["approval.maintainers"]),
          renderDefaultsGroup("Attended notifications", [
            "notifications.target",
            "notifications.destination"
          ]),
          renderDefaultsGroup("Cycle limits", [
            "limits.active_cycles",
            "limits.goal_turns",
            "limits.delegated_workers",
            "limits.research_query_batches",
            "limits.extracted_sources",
            "limits.wall_clock_seconds"
          ]),
          defaultsPreview ? createElement("p", { className: "daidala-workflow-meta" },
            defaultsPreview.valid
              ? "Valid · " + defaultsPreview.source + " · " + defaultsPreview.digest
              : defaultsPreview.reason
          ) : null,
          createElement("div", { className: "daidala-config-actions" },
            createElement("button", {
              type: "button",
              disabled: busy,
              onClick: function () { validateDefaultsDraft(profileName).catch(function () {}); }
            }, "Check defaults"),
            createElement("label", { className: "daidala-pack-confirm" },
              createElement("input", {
                type: "checkbox",
                checked: defaultsConfirmed,
                disabled: !defaultsPreview || !defaultsPreview.valid,
                onChange: function (event) { setDefaultsConfirmed(event.target.checked); }
              }),
              " I confirm writing these registration defaults"
            ),
            createElement("button", {
              type: "button",
              disabled: busy || !defaultsConfirmed || !defaultsPreview || !defaultsPreview.valid,
              onClick: function () { applyDefaultsWizard(profileName); }
            }, "Save registration defaults")
          )
        ) : null
      );
    }

    function renderLinkField(profileName, field, registration, label, pending) {
      var value = fieldUrl(profileName, field, registration, pending);
      return createElement("div", { key: profileName + ":" + field, className: "daidala-github-registration-context" },
        registration ? createElement("dl", null,
          createElement("div", null,
            createElement("dt", null, "Repository"),
            createElement("dd", null, registration.repository_canonical)
          ),
          createElement("div", null,
            createElement("dt", null, "Slug"),
            createElement("dd", null, registration.project_id)
          ),
          createElement("div", null,
            createElement("dt", null, "Board"),
            createElement("dd", null, registration.board + " · " + registration.board_status)
          ),
          createElement("div", null,
            createElement("dt", null, "GitHub Project"),
            createElement("dd", null, registration.github_project_status)
          )
        ) : label === "Register another repository" ? null
          : createElement("p", { className: "daidala-workflow-meta" }, "No repository registered"),
        createElement("label", { className: "daidala-wizard-field" },
          createElement("span", null, label),
          createElement("input", {
            value: value,
            placeholder: "github.com/owner/repository",
            "aria-label": label + " for " + profileName,
            onChange: function (event) { setFieldUrl(profileName, field, event.target.value); }
          })
        ),
        (function () {
          var applyingPolicy = isActive(profileName, field) && bootstrapPreview && !bootstrapPreview.applied;
          var label = busy && isActive(profileName, field)
            ? (applyingPolicy ? "Applying default policy…" : "Inspecting…")
            : applyingPolicy ? "Apply default policy" : "Inspect repository";
          return createElement("button", {
            type: "button",
            disabled: busy || !value.trim() || (applyingPolicy && !confirmed),
            onClick: function () {
              if (applyingPolicy) {
                applyBootstrap();
              } else {
                inspect(profileName, field, registration);
              }
            }
          }, label);
        }()),
        renderPendingLink(profileName, value),
        renderInspectResult(profileName, field)
      );
    }

    function renderProfile(profile) {
      var name = profile.controller_profile;
      var registrations = Array.isArray(profile.registrations) ? profile.registrations : [];
      var pending = pendingBootstraps(name);
      var unmatched = pending.filter(function (row) {
        return !registrations.some(function (registration) {
          return registration.repository_canonical === row.repository_canonical;
        });
      });
      var rows = registrations.map(function (registration) {
        return renderLinkField(name, registration.project_id, registration, "GitHub repository link");
      });
      if (registrations.length) {
        rows.push(renderLinkField(name, "", null, "Register another repository", unmatched[0] || null));
      } else {
        rows.push(renderLinkField(name, "", null, "GitHub repository link", unmatched[0] || null));
      }
      unmatched.slice(1).forEach(function (row) {
        rows.push(renderLinkField(name, "pending:" + row.repository_canonical, null, "GitHub repository link", row));
      });
      return createElement("article", {
        key: name,
        className: "daidala-repository-profile",
        "data-testid": "daidala-repository-profile"
      },
        createElement("h3", null, name),
        profile.status === "unavailable"
          ? createElement("p", { className: "daidala-banner daidala-banner-error" }, "GitHub Repositories are unavailable for this profile.")
          : null,
        renderDefaultsWizard(name, profile.defaults),
        rows
      );
    }

    return createElement("section", { className: "daidala-config", "data-testid": "daidala-repository-registration" },
      createElement("header", { className: "daidala-config-header" },
        createElement("div", null,
          createElement("h2", null, "GitHub Repositories"),
          createElement("p", { className: "daidala-workflow-meta" },
            "Every existing Hermes profile and its registered workspace tuples. Daidala does not accept credentials or paths."
          )
        ),
        createElement("button", { type: "button", disabled: busy, onClick: function () { refreshInventory().catch(function () {}); } }, "Refresh profiles")
      ),
      inventory === undefined
        ? createElement("p", { className: "daidala-workflow-meta" }, "Loading registered projects…")
        : inventory.length === 0
          ? createElement("p", { className: "daidala-workflow-meta" }, "No Hermes profiles are available.")
          : createElement("div", { className: "daidala-repository-profiles" }, inventory.map(renderProfile))
    );
  }

  function GitHubProjectLinksPanel() {
    var registrationsState = useState(undefined);
    var registrations = registrationsState[0];
    var setRegistrations = registrationsState[1];
    var linksState = useState(undefined);
    var links = linksState[0];
    var setLinks = linksState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];

    function refreshLinks() {
      setError("");
      return Promise.all([buildRegistrations(), buildGitHubProjectLinks()])
        .then(function (results) {
          setRegistrations(results[0]);
          setLinks(results[1]);
        })
        .catch(function (caught) {
          setError(errorText(caught));
          setRegistrations([]);
          setLinks([]);
          throw caught;
        });
    }

    useEffect(function () {
      refreshLinks().catch(function () {});
    }, []);

    return createElement(
      "section",
      { className: "daidala-config", "data-testid": "daidala-github-project-links" },
      createElement(
        "header",
        { className: "daidala-config-header" },
        createElement("div", null,
          createElement("h2", null, "GitHub Projects"),
          createElement("p", { className: "daidala-workflow-meta" },
            "One verified Projects v2 link per registered project. Links are profile-local metadata."
          )
        ),
        createElement("button", { type: "button", onClick: function () { refreshLinks().catch(function () {}); } }, "Refresh links")
      ),
      registrations === undefined || links === undefined
        ? createElement("p", { className: "daidala-state daidala-state-loading" }, "Loading GitHub Projects")
        : error
          ? createElement("p", { className: "daidala-banner daidala-banner-error" }, error)
          : registrations.length === 0
            ? createElement("p", { className: "daidala-state daidala-state-empty" }, "No registered projects")
            : createElement(
                "div",
                { className: "daidala-github-project-links-grid" },
                registrations.map(function (registration) {
                  var link = links.filter(function (row) {
                    return row.project_id === registration.project_id;
                  })[0] || null;
                  return createElement(GitHubProjectLinkCard, {
                    key: registration.project_id,
                    registration: registration,
                    link: link,
                    onChanged: refreshLinks
                  });
                })
              )
    );
  }

  function linkIssueLabel(message) {
    var normalized = String(message || "").toLowerCase();
    if (normalized.indexOf("credential") !== -1 || normalized.indexOf("binding") !== -1 || normalized.indexOf("capability") !== -1) {
      return "GitHub Project read capability blocked";
    }
    if (normalized.indexOf("node") !== -1 || normalized.indexOf("stale") !== -1) {
      return "GitHub Project link is stale";
    }
    if (normalized.indexOf("not found") !== -1 || normalized.indexOf("inaccessible") !== -1) {
      return "GitHub Project is unavailable";
    }
    return "GitHub Project operation blocked";
  }

  function linkIssueMessage(reason) {
    var message = errorText(reason);
    var payloadStart = message.indexOf("{");
    if (payloadStart !== -1) {
      try {
        var payload = JSON.parse(message.slice(payloadStart));
        if (payload && typeof payload.detail === "string") message = payload.detail;
      } catch (_error) {}
    }
    return linkIssueLabel(message) + ": " + message;
  }

  function linkSummary(link) {
    return link
      ? link.owner + " · #" + String(link.project_number) + " · " + link.project_node_id
      : "No GitHub Project configured";
  }

  function GitHubProjectLinkCard(props) {
    var registration = props.registration;
    var ownerState = useState(props.link ? props.link.owner : "");
    var owner = ownerState[0];
    var setOwner = ownerState[1];
    var numberState = useState(props.link ? String(props.link.project_number) : "");
    var number = numberState[0];
    var setNumber = numberState[1];
    var previewState = useState(null);
    var preview = previewState[0];
    var setPreview = previewState[1];
    var verificationState = useState(null);
    var verification = verificationState[0];
    var setVerification = verificationState[1];
    var removalState = useState(null);
    var removal = removalState[0];
    var setRemoval = removalState[1];
    var applyConfirmedState = useState(false);
    var applyConfirmed = applyConfirmedState[0];
    var setApplyConfirmed = applyConfirmedState[1];
    var removeConfirmedState = useState(false);
    var removeConfirmed = removeConfirmedState[0];
    var setRemoveConfirmed = removeConfirmedState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];

    function payload() {
      var parsedNumber = number.trim();
      if (!owner.trim() || !/^[1-9][0-9]*$/.test(parsedNumber)) return null;
      return {
        project_id: registration.project_id,
        owner: owner.trim(),
        project_number: Number(parsedNumber)
      };
    }

    function invalidatePreview() {
      setPreview(null);
      setApplyConfirmed(false);
      setRemoval(null);
      setRemoveConfirmed(false);
    }

    function previewChange() {
      var request = payload();
      if (!request) {
        setMessage("Owner and a positive Project number are required.");
        return;
      }
      setBusy(true);
      setMessage("");
      previewGitHubProjectLink(request)
        .then(function (value) {
          setPreview(value);
          setVerification(null);
          setRemoval(null);
          setApplyConfirmed(false);
        })
        .catch(function (caught) {
          setPreview(null);
          setMessage(linkIssueMessage(caught));
        })
        .finally(function () { setBusy(false); });
    }

    function verifyLink() {
      if (!props.link) return;
      setBusy(true);
      setMessage("");
      verifyGitHubProjectLink(registration.project_id)
        .then(function (value) {
          setVerification(value);
          if (value.healthy) setMessage("GitHub Project verified for this session.");
          else setMessage(linkIssueLabel(value.reason) + ": " + value.reason);
        })
        .catch(function (caught) {
          setVerification(null);
          setMessage(linkIssueMessage(caught));
        })
        .finally(function () { setBusy(false); });
    }

    function applyLink() {
      if (!preview || !applyConfirmed) return;
      setBusy(true);
      setMessage("");
      replaceGitHubProjectLink(registration.project_id, {
        owner: preview.link.owner,
        project_number: preview.link.project_number,
        preview_digest: preview.preview_digest,
        confirm: true
      })
        .then(function () {
          setOwner(preview.link.owner);
          setNumber(String(preview.link.project_number));
          setPreview(null);
          setApplyConfirmed(false);
          setVerification(null);
          setMessage("GitHub Project link saved.");
          return props.onChanged();
        })
        .catch(function (caught) {
          setMessage(linkIssueMessage(caught));
        })
        .finally(function () { setBusy(false); });
    }

    function previewRemoval() {
      if (!props.link) return;
      setBusy(true);
      setMessage("");
      readGitHubProjectLink(registration.project_id)
        .then(function (value) {
          setRemoval(value);
          setPreview(null);
          setRemoveConfirmed(false);
        })
        .catch(function (caught) {
          setRemoval(null);
          setMessage(linkIssueMessage(caught));
        })
        .finally(function () { setBusy(false); });
    }

    function removeLink() {
      if (!removal || !removeConfirmed) return;
      setBusy(true);
      setMessage("");
      removeGitHubProjectLink(registration.project_id, {
        delete_preview_digest: removal.delete_preview_digest,
        confirm: true
      })
        .then(function () {
          setOwner("");
          setNumber("");
          setRemoval(null);
          setRemoveConfirmed(false);
          setVerification(null);
          setMessage("GitHub Project link removed.");
          return props.onChanged();
        })
        .catch(function (caught) {
          setMessage(linkIssueMessage(caught));
        })
        .finally(function () { setBusy(false); });
    }

    return createElement(
      "article",
      {
        className: "daidala-github-project-link",
        "data-testid": "daidala-github-project-link",
        "data-project-id": registration.project_id
      },
      createElement("header", { className: "daidala-github-project-link-header" },
        createElement("div", null,
          createElement("h3", null, registration.project_id),
          props.link
            ? createElement("p", { className: "daidala-workflow-meta" }, linkSummary(props.link))
            : null
        ),
        props.link
          ? createElement("button", { type: "button", disabled: busy, onClick: verifyLink }, "Verify")
          : null
      ),
      createElement("section", { className: "daidala-github-registration-context" },
        createElement("h4", null, "Registration context"),
        createElement("dl", null,
          createElement("div", null, createElement("dt", null, "Repository"), createElement("dd", null, registration.repository_canonical)),
          createElement("div", null, createElement("dt", null, "Verified remote"), createElement("dd", null, registration.verified_remote)),
          createElement("div", null, createElement("dt", null, "Checkout configuration"), createElement("dd", null,
            registration.checkout_match ? "Matches registration" : "Does not match registration"
          ))
        )
      ),
      props.link
        ? createElement("section", { className: "daidala-github-current-link" },
            createElement("h4", null, "Current Projects v2 link"),
            createElement("dl", null,
              createElement("div", null, createElement("dt", null, "Owner / number"), createElement("dd", null, props.link.owner + " · #" + props.link.project_number)),
              createElement("div", null, createElement("dt", null, "Node ID"), createElement("dd", { className: "daidala-skill-digest" }, props.link.project_node_id))
            ),
            createElement("button", { type: "button", disabled: busy, onClick: previewRemoval }, "Preview removal")
          )
        : createElement("p", { className: "daidala-state daidala-state-empty" }, "No GitHub Project configured"),
      createElement("section", { className: "daidala-github-link-form" },
        createElement("h4", null, props.link ? "Edit GitHub Project link" : "Add GitHub Project link"),
        createElement("label", { className: "daidala-github-field" },
          createElement("span", null, "Projects owner"),
          createElement("input", {
            value: owner,
            maxLength: 39,
            onChange: function (event) { setOwner(event.target.value); invalidatePreview(); },
            "aria-label": "GitHub Projects owner for " + registration.project_id
          })
        ),
        createElement("label", { className: "daidala-github-field" },
          createElement("span", null, "Project number"),
          createElement("input", {
            type: "number", min: 1, step: 1, value: number,
            onChange: function (event) { setNumber(event.target.value); invalidatePreview(); },
            "aria-label": "GitHub Project number for " + registration.project_id
          })
        ),
        createElement("button", { type: "button", disabled: busy, onClick: previewChange }, "Preview link change")
      ),
      preview
        ? createElement("section", { className: "daidala-github-link-preview" },
            createElement("h4", null, "Preview link change"),
            createElement("p", { className: "daidala-skill-digest" }, "Preview digest " + preview.preview_digest),
            createElement("p", null, "Current: " + linkSummary(props.link)),
            createElement("p", null, "Proposed: " + linkSummary(preview.link)),
            createElement("p", null, "Resolved Project: " + (preview.project.title || "title unavailable")),
            createElement("p", null, "Resolved URL: " + (preview.project.url || "URL unavailable")),
            createElement("label", { className: "daidala-pack-confirm" },
              createElement("input", {
                type: "checkbox", checked: applyConfirmed,
                onChange: function (event) { setApplyConfirmed(event.target.checked); }
              }),
              "I confirm applying this exact verified link"
            ),
            createElement("button", { type: "button", disabled: busy || !applyConfirmed, onClick: applyLink }, "Apply link")
          )
        : null,
      removal
        ? createElement("section", { className: "daidala-github-link-preview" },
            createElement("h4", null, "Remove GitHub Project link"),
            createElement("p", null, linkSummary(removal.link)),
            createElement("label", { className: "daidala-pack-confirm" },
              createElement("input", {
                type: "checkbox", checked: removeConfirmed,
                onChange: function (event) { setRemoveConfirmed(event.target.checked); }
              }),
              "I confirm removing this GitHub Project link"
            ),
            createElement("button", { type: "button", disabled: busy || !removeConfirmed, onClick: removeLink }, "Remove link")
          )
        : null,
      verification
        ? createElement("p", { className: verification.healthy ? "daidala-github-verified" : "daidala-banner daidala-banner-error" },
            verification.healthy
              ? "GitHub Project verified for this session: " + (verification.project.title || "title unavailable")
              : linkIssueLabel(verification.reason) + ": " + verification.reason
          )
        : null,
      message ? createElement("p", { role: "status" }, message) : null
    );
  }

  function PackBrowser() {
    var inventoryState = useState(undefined);
    var inventory = inventoryState[0];
    var setInventory = inventoryState[1];
    var selectedState = useState("");
    var selectedName = selectedState[0];
    var setSelectedName = selectedState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];

    function refreshPacks() {
      setError("");
      buildPacks()
        .then(function (value) {
          setInventory(value);
          setSelectedName(function (current) {
            if (value.packs.some(function (pack) { return pack.name === current; })) {
              return current;
            }
            return value.packs.length ? value.packs[0].name : "";
          });
        })
        .catch(function (caught) {
          setError(caught.message);
          setInventory({ profile: "unavailable", packs: [] });
        });
    }

    useEffect(function () {
      refreshPacks();
    }, []);

    var packs = inventory ? inventory.packs : [];
    var selectedPack = packs.filter(function (pack) { return pack.name === selectedName; })[0];

    return createElement(
      "section",
      { className: "daidala-config daidala-pack-workspace", "data-testid": "daidala-pack-browser" },
      createElement(
        "header",
        { className: "daidala-config-header" },
        createElement("div", null,
          createElement("p", { className: "daidala-eyebrow" }, "Configuration"),
          createElement("h2", null, "Workflow packs"),
          createElement("p", { className: "daidala-workflow-meta" },
            "Install a complete immutable catalog once; activate only the skills each lifecycle stage needs."
          )
        ),
        createElement("label", { className: "daidala-pack-selector" },
          createElement("span", null, "Pack"),
          createElement("select", {
            value: selectedName,
            disabled: inventory === undefined || packs.length === 0,
            onChange: function (event) { setSelectedName(event.target.value); }
          },
            packs.length === 0
              ? createElement("option", { value: "" }, "No pack available")
              : packs.map(function (pack) {
                  return createElement("option", { key: pack.name, value: pack.name }, pack.name);
                })
          )
        )
      ),
      inventory === undefined
        ? createElement("div", { className: "daidala-pack-loading", role: "status" },
            createElement("p", { className: "daidala-state daidala-state-loading" }, "Loading pack catalog and readiness"),
            createElement("div", { className: "daidala-pack-loading-summary" })
          )
        : error
          ? createElement("div", { className: "daidala-state daidala-state-unavailable" },
              createElement("p", null, "Pack inventory unavailable: " + error),
              createElement("button", { type: "button", onClick: refreshPacks }, "Retry validation")
            )
          : selectedPack
            ? createElement(PackCard, {
                key: selectedPack.name,
                pack: selectedPack,
                profile: inventory.profile
              })
            : createElement("p", { className: "daidala-state daidala-state-empty" },
                "Select a workflow pack to inspect installation and lifecycle readiness."
              )
    );
  }

  function PackCard(props) {
    var pack = props.pack;
    var profile = props.profile;
    var checkState = useState(null);
    var check = checkState[0];
    var setCheck = checkState[1];
    var installPreviewState = useState(null);
    var installPreview = installPreviewState[0];
    var setInstallPreview = installPreviewState[1];
    var installProgressState = useState(null);
    var installProgress = installProgressState[0];
    var setInstallProgress = installProgressState[1];
    var actionPreviewState = useState(null);
    var actionPreview = actionPreviewState[0];
    var setActionPreview = actionPreviewState[1];
    var failureState = useState(null);
    var failure = failureState[0];
    var setFailure = failureState[1];
    var failureOpenState = useState(false);
    var failureOpen = failureOpenState[0];
    var setFailureOpen = failureOpenState[1];
    var documentState = useState(null);
    var documentView = documentState[0];
    var setDocumentView = documentState[1];
    var searchState = useState("");
    var search = searchState[0];
    var setSearch = searchState[1];
    var catalogOnlyState = useState(false);
    var catalogOnly = catalogOnlyState[0];
    var setCatalogOnly = catalogOnlyState[1];
    var showAllNarrowState = useState(false);
    var showAllNarrow = showAllNarrowState[0];
    var setShowAllNarrow = showAllNarrowState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];
    var readinessErrorState = useState("");
    var readinessError = readinessErrorState[0];
    var setReadinessError = readinessErrorState[1];
    var installInvokerRef = useRef(null);
    var actionInvokerRef = useRef(null);
    var actionReturnsToDetailRef = useRef(false);
    var detailInvokerRef = useRef(null);
    var modalHeadingRef = useRef(null);
    var detailHeadingRef = useRef(null);
    var projection = check || pack;
    var stages = Array.isArray(projection.stages) ? projection.stages : [];
    var catalog = Array.isArray(projection.skills) ? projection.skills : [];
    var stageBySkill = {};
    stages.forEach(function (stage) {
      stage.skills.forEach(function (skill) {
        if (!stageBySkill[skill.name]) stageBySkill[skill.name] = [];
        stageBySkill[skill.name].push({ id: stage.id, activation: skill.activation });
      });
    });
    var missingCount = check ? catalog.filter(function (skill) {
      return skill.external && !skill.installed;
    }).length : 0;
    var installedCount = check ? catalog.filter(function (skill) { return skill.installed; }).length : 0;
    var disabledCount = check ? catalog.filter(function (skill) {
      return skill.installed && skill.enabled === false;
    }).length : 0;
    var warningCount = check ? catalog.filter(function (skill) {
      return skill.installed && skill.observed_digest && skill.observed_digest !== skill.expected_digest;
    }).length : 0;
    var stageMappedCount = catalog.filter(function (skill) {
      return Array.isArray(stageBySkill[skill.name]) && stageBySkill[skill.name].length > 0;
    }).length;
    var catalogOnlyCount = catalog.length - stageMappedCount;
    var normalizedSearch = search.trim().toLowerCase();
    var filteredSkills = catalog.filter(function (skill) {
      var bindings = stageBySkill[skill.name] || [];
      if (catalogOnly && bindings.length > 0) return false;
      if (!normalizedSearch) return true;
      return (
        skill.name.toLowerCase().indexOf(normalizedSearch) >= 0 ||
        (bindings.length ? bindings.map(function (binding) { return binding.id; }).join(" ") : "catalog-only")
          .indexOf(normalizedSearch) >= 0
      );
    });
    var visibleSkillCount = showAllNarrow
      ? filteredSkills.length
      : Math.min(filteredSkills.length, 4);
    var documentAction = null;
    var documentActionLabel = null;
    if (documentView && documentView.installed) {
      if (documentView.enabled === false) {
        documentAction = "enable";
        documentActionLabel = "Enable for " + profile;
      } else if (documentView.enabled === true) {
        documentAction = "disable";
        documentActionLabel = "Disable for " + profile;
      }
    }
    var status = failure
      ? "Action failed"
      : !check
        ? readinessError
          ? "Check unavailable"
          : "Checking readiness"
      : check.ready
        ? warningCount
          ? "Ready with warnings"
          : "Ready"
        : "Blocked";

    useEffect(function () {
      var cancelled = false;
      setBusy(true);
      setReadinessError("");
      setInstallProgress(null);
      checkPack(pack.name)
        .then(function (value) {
          if (!cancelled) setCheck(value);
        })
        .catch(function (caught) {
          if (!cancelled) setReadinessError(errorText(caught));
        })
        .finally(function () {
          if (!cancelled) setBusy(false);
        });
      return function () { cancelled = true; };
    }, [pack.name]);

    useEffect(function () {
      if ((installPreview || actionPreview) && modalHeadingRef.current) {
        modalHeadingRef.current.focus();
      }
    }, [installPreview, actionPreview]);

    useEffect(function () {
      if (documentView && detailHeadingRef.current) detailHeadingRef.current.focus();
    }, [documentView]);

    function run(action, successMessage) {
      setBusy(true);
      setMessage("");
      return Promise.resolve(action())
        .then(function (value) {
          if (successMessage) setMessage(successMessage);
          return value;
        })
        .catch(function (caught) {
          setMessage(caught.message);
          throw caught;
        })
        .finally(function () { setBusy(false); });
    }

    function returnFocus(reference) {
      window.setTimeout(function () {
        if (reference.current) reference.current.focus();
      }, 0);
    }

    function runCheck() {
      run(function () { return checkPack(pack.name); }, "Readiness check complete.")
        .then(function (value) {
          setCheck(value);
          setReadinessError("");
          setFailure(null);
        })
        .catch(function () {});
    }

    function openInstallPreview(event) {
      installInvokerRef.current = event.currentTarget;
      run(
        function () { return previewPackInstall(pack.name); },
        "Review the exact shared installation before applying it."
      )
        .then(function (value) {
          setCheck(value);
          setInstallPreview(value);
        })
        .catch(function () {});
    }

    function closeInstallPreview() {
      setInstallPreview(null);
      returnFocus(installInvokerRef);
    }

    function applyInstall() {
      if (!installPreview) return;
      setBusy(true);
      setMessage("");
      setInstallProgress(null);
      streamPackInstall(pack.name, installPreview, setInstallProgress)
        .then(function (value) {
          setCheck(value.pack);
          setFailure(null);
          setInstallPreview(null);
          setInstallProgress(null);
          setMessage("Pack installation applied and post-verified.");
          returnFocus(installInvokerRef);
        })
        .catch(function (caught) {
          setInstallProgress(null);
          var structured = packInstallFailure(caught);
          if (structured && structured.receipt) {
            setFailure(structured.receipt);
            setFailureOpen(false);
            if (structured.receipt.pack_state) setCheck(structured.receipt.pack_state);
            setInstallPreview(null);
            setMessage(structured.message);
            returnFocus(installInvokerRef);
            return;
          }
          if (errorText(caught).indexOf("changed after preview") >= 0) {
            return previewPackInstall(pack.name).then(function (fresh) {
              setCheck(fresh);
              setInstallPreview(fresh);
              setMessage("Pack state changed. Review this refreshed preview before confirming again.");
            });
          }
          setMessage(errorText(caught));
        })
        .finally(function () { setBusy(false); });
    }

    function openActionPreview(event, action, skillName) {
      actionInvokerRef.current = event.currentTarget;
      actionReturnsToDetailRef.current = Boolean(documentView);
      run(
        function () { return previewPackSkillAction(pack.name, action, skillName); },
        "Review the profile-local availability change before applying it."
      )
        .then(function (value) {
          setCheck(value.pack);
          setActionPreview(value);
        })
        .catch(function () {});
    }

    function closeActionPreview() {
      setActionPreview(null);
      returnFocus(actionReturnsToDetailRef.current ? detailHeadingRef : actionInvokerRef);
    }

    function applyAvailability() {
      if (!actionPreview) return;
      run(
        function () { return applyPackSkillAction(pack.name, actionPreview); },
        "Profile-local availability updated and verified."
      )
        .then(function (value) {
          setCheck(value.pack);
          setActionPreview(null);
          if (documentView && value.affected.indexOf(documentView.skill) !== -1) {
            return buildPackSkillContent(pack.name, documentView.skill).then(setDocumentView);
          }
          return null;
        })
        .then(function () {
          returnFocus(actionReturnsToDetailRef.current ? detailHeadingRef : actionInvokerRef);
        })
        .catch(function (caught) {
          if (errorText(caught).indexOf("changed after preview") >= 0) {
            previewPackSkillAction(
              pack.name, actionPreview.action, actionPreview.skill_name
            ).then(function (fresh) {
              setCheck(fresh.pack);
              setActionPreview(fresh);
              setMessage("Pack state changed. Review this refreshed preview before confirming again.");
            });
          }
        });
    }

    function loadContent(event, skillName) {
      detailInvokerRef.current = event.currentTarget;
      run(function () { return buildPackSkillContent(pack.name, skillName); }, null)
        .then(setDocumentView)
        .catch(function () {});
    }

    function closeDocument() {
      setDocumentView(null);
      returnFocus(detailInvokerRef);
    }

    function trapDialogFocus(event, close) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab") return;
      var dialog = event.currentTarget.querySelector('[role="dialog"]');
      if (!dialog) return;
      var controls = dialog.querySelectorAll(
        "[tabindex=\"-1\"], button:not([disabled]), input:not([disabled]), a[href], select:not([disabled])"
      );
      if (!controls.length) return;
      var first = controls[0];
      var last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    return createElement(
      "article",
      { className: "daidala-pack", "data-testid": "daidala-pack", "data-pack": pack.name },
      createElement("section", { className: "daidala-pack-overview" },
        createElement("header", { className: "daidala-pack-header" },
          createElement("div", null,
            createElement("p", { className: "daidala-eyebrow" }, "Selected workflow pack"),
            createElement("h3", null, pack.name),
            createElement("p", { className: "daidala-workflow-meta" },
              pack.source + " @ " + pack.source_revision.slice(0, 12)
            )
          ),
          createElement("span", {
            className: "daidala-pack-status is-" + status.toLowerCase().replace(/ /g, "-")
          }, status)
        ),
        createElement("div", { className: "daidala-pack-command-row" },
          createElement("button", {
            type: "button",
            className: "daidala-pack-primary",
            disabled: busy || !check || missingCount === 0,
            onClick: openInstallPreview
          }, failure
            ? "Retry " + missingCount + " missing skills"
            : missingCount
              ? (installedCount ? "Install " + missingCount + " missing skills" : "Install pack")
              : "Pack installed"
          ),
          createElement("button", { type: "button", disabled: busy, onClick: runCheck },
            busy ? "Checking…" : "Refresh readiness"
          )
        ),
        installProgress ? createElement("div", {
          className: "daidala-pack-install-progress",
          role: "status",
          "aria-live": "polite",
          "data-testid": "daidala-pack-install-progress"
        },
          createElement("strong", null,
            "Installing skill " + installProgress.position + " / " + installProgress.total
          ),
          createElement("span", null, installProgress.skill)
        ) : null,
        createElement("dl", { className: "daidala-pack-stats" },
          createElement("div", null,
            createElement("dt", null, "Catalog"),
            createElement("dd", null, String(catalog.length) + " skills")
          ),
          createElement("div", null,
            createElement("dt", null, "Installed"),
            createElement("dd", null, check ? installedCount + " / " + catalog.length : "Checking")
          ),
          createElement("div", null,
            createElement("dt", null, "Active profile"),
            createElement("dd", null, profile)
          ),
          createElement("div", null,
            createElement("dt", null, "Digest warnings"),
            createElement("dd", null, check ? String(warningCount) : "Checking")
          )
        ),
        createElement("div", { className: "daidala-pack-lifecycle" },
          createElement("div", { className: "daidala-pack-section-heading" },
            createElement("div", null,
              createElement("h4", null, "Lifecycle"),
              createElement("p", null, "Stage bindings select activation; the catalog owns installation.")
            ),
            createElement("span", null, catalogOnlyCount + " catalog-only")
          ),
          createElement("ol", null,
            stages.map(function (stage) {
              return createElement("li", { key: stage.id },
                createElement("span", null, stage.id),
                createElement("strong", null, stage.skills.length)
              );
            })
          )
        )
      ),
      readinessError
        ? createElement("section", { className: "daidala-pack-state-panel is-unavailable" },
            createElement("strong", null, "Readiness check unavailable"),
            createElement("p", null, readinessError),
            createElement("button", { type: "button", onClick: runCheck }, "Retry readiness check")
          )
        : null,
      failure
        ? createElement("section", { className: "daidala-pack-state-panel is-failed" },
            createElement("div", null,
              createElement("strong", null, "Pack action failed"),
              createElement("p", null,
                failure.succeeded.length + " installed · " + failure.failed.length + " failed. " +
                "Successful installs remain; retry targets only the fresh missing set."
              )
            ),
            createElement("button", {
              type: "button",
              onClick: function () { setFailureOpen(!failureOpen); }
            }, failureOpen ? "Hide failure receipt" : "View failure receipt"),
            failureOpen
              ? createElement("div", { className: "daidala-pack-receipt" },
                  createElement("p", null, "Failed: " + failure.failed.join(", ")),
                  createElement("p", null, "Succeeded: " + failure.succeeded.join(", ")),
                  createElement("p", { className: "daidala-skill-digest" },
                    "Source revision " + failure.source_revision
                  )
                )
              : null
          )
        : null,
      check && disabledCount
        ? createElement("section", { className: "daidala-pack-availability" },
            createElement("div", null,
              createElement("strong", null, disabledCount + " installed skill(s) disabled"),
              createElement("p", null, "Availability changes only profile “" + profile + "”.")
            ),
            createElement("button", {
              type: "button",
              disabled: busy || profile === "unavailable",
              onClick: function (event) { openActionPreview(event, "enable", null); }
            }, "Enable " + disabledCount + " for " + profile)
          )
        : null,
      createElement("section", { className: "daidala-pack-inventory" },
        createElement("div", { className: "daidala-pack-section-heading" },
          createElement("div", null,
            createElement("h4", null, "Skill inventory"),
            createElement("p", null,
              stageMappedCount + " stage-mapped · " + catalogOnlyCount + " catalog-only"
            )
          ),
          createElement("span", { className: "daidala-pack-shown" },
            createElement("span", { className: "is-wide" }, filteredSkills.length + " shown"),
            createElement("span", { className: "is-narrow" },
              visibleSkillCount + " of " + filteredSkills.length + " shown"
            )
          )
        ),
        createElement("div", { className: "daidala-pack-filters" },
          createElement("label", null,
            createElement("span", null, "Search skills"),
            createElement("input", {
              type: "search",
              value: search,
              placeholder: "Search skills or lifecycle stage",
              onChange: function (event) {
                setSearch(event.target.value);
                setShowAllNarrow(false);
              }
            })
          ),
          createElement("button", {
            type: "button",
            className: catalogOnly ? "is-active" : "",
            "aria-pressed": catalogOnly,
            onClick: function () {
              setCatalogOnly(!catalogOnly);
              setShowAllNarrow(false);
            }
          }, "Catalog-only " + catalogOnlyCount)
        ),
        createElement("div", {
          className: "daidala-pack-table-wrap" + (showAllNarrow ? " is-expanded" : "")
        },
          createElement("table", null,
            createElement("thead", null,
              createElement("tr", null,
                createElement("th", { scope: "col" }, "Skill"),
                createElement("th", { scope: "col" }, "Status"),
                createElement("th", { scope: "col" }, "Lifecycle role"),
                createElement("th", { scope: "col" }, "Activation"),
                createElement("th", { scope: "col" }, "")
              )
            ),
            createElement("tbody", null,
              filteredSkills.map(function (skill) {
                var bindings = stageBySkill[skill.name] || [];
                var mismatch = skill.installed && skill.observed_digest &&
                  skill.observed_digest !== skill.expected_digest;
                var skillStatus = !check
                  ? "Checking"
                  : !skill.installed
                    ? "Not installed"
                    : skill.enabled === false
                      ? "Disabled"
                      : mismatch
                        ? "Ready with warning"
                        : "Ready";
                return createElement("tr", { key: skill.name },
                  createElement("th", { scope: "row" },
                    createElement("span", { className: "daidala-skill-name" }, skill.name),
                    bindings.length === 0
                      ? createElement("span", { className: "daidala-catalog-only" }, "Catalog only")
                      : null
                  ),
                  createElement("td", null,
                    createElement("span", {
                      className: "daidala-skill-status is-" + skillStatus.toLowerCase().replace(/ /g, "-")
                    }, skillStatus)
                  ),
                  createElement("td", null,
                    bindings.length
                      ? bindings.map(function (binding) { return binding.id; }).join(", ")
                      : "Available outside lifecycle"
                  ),
                  createElement("td", null,
                    bindings.length
                      ? bindings.map(function (binding) { return binding.activation; }).join(", ")
                      : "Manual"
                  ),
                  createElement("td", null,
                    createElement("button", {
                      type: "button",
                      className: "daidala-row-action",
                      onClick: function (event) { loadContent(event, skill.name); }
                    }, "Details")
                  )
                );
              })
            )
          )
        ),
        filteredSkills.length > 4
          ? createElement("button", {
              type: "button",
              className: "daidala-pack-disclosure",
              "aria-expanded": showAllNarrow,
              onClick: function () { setShowAllNarrow(!showAllNarrow); }
            }, showAllNarrow ? "Show fewer skills" : "Show all " + filteredSkills.length + " skills")
          : null,
        filteredSkills.length === 0
          ? createElement("p", { className: "daidala-state daidala-state-empty" },
              "No skills match the current search and filter."
            )
          : null
      ),
      documentView && !actionPreview
        ? createElement("div", {
            className: "daidala-pack-drawer-layer",
            onKeyDown: function (event) { trapDialogFocus(event, closeDocument); }
          },
            createElement("button", {
              type: "button",
              className: "daidala-pack-drawer-backdrop",
              "aria-label": "Close skill details",
              onClick: closeDocument
            }),
            createElement("aside", {
              className: "daidala-pack-drawer",
              role: "dialog",
              "aria-modal": "true",
              "aria-labelledby": "daidala-skill-detail-title",
              "data-testid": "daidala-skill-content"
            },
              createElement("header", null,
                createElement("div", null,
                  createElement("p", { className: "daidala-eyebrow" }, "Skill detail"),
                  createElement("h4", {
                    id: "daidala-skill-detail-title", ref: detailHeadingRef, tabIndex: -1
                  }, documentView.skill)
                ),
                createElement("button", { type: "button", onClick: closeDocument }, "Close")
              ),
              createElement("dl", { className: "daidala-pack-detail-grid" },
                createElement("div", null,
                  createElement("dt", null, "Installation"),
                  createElement("dd", null, documentView.installed ? "Installed" : "Not installed")
                ),
                createElement("div", null,
                  createElement("dt", null, "Profile " + profile),
                  createElement("dd", null,
                    documentView.installed
                      ? documentView.enabled === false ? "Disabled" : "Enabled"
                      : "Unavailable"
                  )
                ),
                createElement("div", null,
                  createElement("dt", null, "Lifecycle"),
                  createElement("dd", null,
                    documentView.stages.length
                      ? documentView.stages.join(", ")
                      : "Catalog-only"
                  )
                ),
                createElement("div", null,
                  createElement("dt", null, "Activation"),
                  createElement("dd", null,
                    documentView.activation.length
                      ? documentView.activation.join(", ")
                      : "Manual"
                  )
                )
              ),
              documentView.observed_digest && documentView.observed_digest !== documentView.expected_digest
                ? createElement("div", { className: "daidala-banner daidala-banner-warning" },
                    "Digest mismatch warning. The installed skill remains available."
                  )
                : null,
              createElement("section", { className: "daidala-pack-detail-source" },
                createElement("h5", null, "Pinned source"),
                createElement("a", {
                  href: documentView.source_url,
                  target: "_blank",
                  rel: "noreferrer"
                }, "Open immutable source"),
                createElement("p", { className: "daidala-skill-digest" },
                  "Expected " + documentView.expected_digest +
                  (documentView.observed_digest ? " · observed " + documentView.observed_digest : "")
                )
              ),
              createElement("section", { className: "daidala-pack-detail-content" },
                createElement("h5", null, "SKILL.md"),
                documentView.available
                  ? createElement("pre", null, documentView.content)
                  : createElement("p", { className: "daidala-banner daidala-banner-warning" },
                      documentView.installed
                        ? "The installed document is unavailable."
                        : "Install this skill through the pack-wide action."
                    )
              ),
              documentAction
                ? createElement("footer", null,
                    createElement("button", {
                      type: "button",
                      disabled: busy || profile === "unavailable",
                      onClick: function (event) {
                        openActionPreview(event, documentAction, documentView.skill);
                      }
                    }, documentActionLabel)
                  )
                : null
            )
          )
        : null,
      installPreview
        ? createElement("div", {
            className: "daidala-pack-modal-layer",
            onKeyDown: function (event) { trapDialogFocus(event, closeInstallPreview); }
          },
            createElement("section", {
              className: "daidala-pack-modal",
              role: "dialog",
              "aria-modal": "true",
              "aria-labelledby": "daidala-install-title",
              "data-testid": "daidala-pack-install-preview"
            },
              createElement("p", { className: "daidala-eyebrow" }, "Confirm shared installation"),
              createElement("h4", {
                id: "daidala-install-title", ref: modalHeadingRef, tabIndex: -1
              }, installedCount ? "Install missing pack skills?" : "Install workflow pack?"),
              createElement("p", null,
                "This installs " + installPreview.actions.length + " immutable skill target(s) into the shared Hermes skill store."
              ),
              createElement("dl", { className: "daidala-pack-preview-grid" },
                createElement("div", null,
                  createElement("dt", null, "Pack"), createElement("dd", null, pack.name)
                ),
                createElement("div", null,
                  createElement("dt", null, "Revision"),
                  createElement("dd", null, installPreview.source_revision.slice(0, 12))
                ),
                createElement("div", null,
                  createElement("dt", null, "Install scope"),
                  createElement("dd", null, installPreview.actions.length + " missing targets")
                ),
                createElement("div", null,
                  createElement("dt", null, "Profile effect"),
                  createElement("dd", null, profile + " availability unchanged")
                )
              ),
              createElement("div", { className: "daidala-banner daidala-banner-warning" },
                "Partial external failure is possible. Successful installs remain; a fresh retry offers only missing targets."
              ),
              createElement("p", { className: "daidala-skill-digest" },
                "Fresh preview " + installPreview.preview_digest
              ),
              createElement("footer", null,
                createElement("button", { type: "button", disabled: busy, onClick: closeInstallPreview }, "Cancel"),
                createElement("button", {
                  type: "button",
                  className: "daidala-pack-primary",
                  disabled: busy || installPreview.actions.length === 0,
                  onClick: applyInstall
                }, "Install " + installPreview.actions.length + " skills")
              )
            )
          )
        : null,
      actionPreview
        ? createElement("div", {
            className: "daidala-pack-modal-layer",
            onKeyDown: function (event) { trapDialogFocus(event, closeActionPreview); }
          },
            createElement("section", {
              className: "daidala-pack-modal",
              role: "dialog",
              "aria-modal": "true",
              "aria-labelledby": "daidala-availability-title",
              "data-testid": "daidala-pack-preview"
            },
              createElement("p", { className: "daidala-eyebrow" }, "Confirm profile-local change"),
              createElement("h4", {
                id: "daidala-availability-title", ref: modalHeadingRef, tabIndex: -1
              }, (actionPreview.action === "enable" ? "Enable " : "Disable ") +
                actionPreview.skills.length + " skill(s) for “" + profile + "”?"
              ),
              createElement("p", null,
                "Installation and every other Hermes profile remain unchanged."
              ),
              createElement("ul", null,
                actionPreview.skills.map(function (skill) {
                  return createElement("li", { key: skill }, skill);
                })
              ),
              actionPreview.blockers.length
                ? createElement("p", { className: "daidala-banner daidala-banner-error" },
                    actionPreview.blockers.join("; ")
                  )
                : null,
              createElement("p", { className: "daidala-skill-digest" },
                "Fresh preview " + actionPreview.preview_digest
              ),
              createElement("footer", null,
                createElement("button", { type: "button", disabled: busy, onClick: closeActionPreview }, "Cancel"),
                createElement("button", {
                  type: "button",
                  className: "daidala-pack-primary",
                  disabled: busy || !actionPreview.applicable,
                  onClick: applyAvailability
                }, (actionPreview.action === "enable" ? "Enable " : "Disable ") +
                  actionPreview.skills.length + " for " + profile
                )
              )
            )
          )
        : null,
      message ? createElement("p", { className: "daidala-pack-message", role: "status" }, message) : null
    );
  }

  var WIZARD_STAGES = ["define", "plan", "implement", "verify", "review", "deliver"];
  var WORKFLOW_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;

  function workflowIdentityError(value) {
    var workflowId = value.trim();
    return workflowId && !WORKFLOW_ID_PATTERN.test(workflowId)
      ? "Workflow identity must use 1-128 letters, digits, dots, underscores, or hyphens."
      : "";
  }

  function StartWorkflow(props) {
    var _a = useState(null), inventory = _a[0], setInventory = _a[1];
    var _b = useState(""), error = _b[0], setError = _b[1];
    var _c = useState(false), busy = _c[0], setBusy = _c[1];
    var _d = useState(null), readiness = _d[0], setReadiness = _d[1];
    var _e = useState(null), preview = _e[0], setPreview = _e[1];
    var _f = useState(false), confirmed = _f[0], setConfirmed = _f[1];
    var _g = useState(null), boardPreview = _g[0], setBoardPreview = _g[1];
    var _h = useState(false), boardConfirmed = _h[0], setBoardConfirmed = _h[1];
    var _i = useState(0), reload = _i[0], setReload = _i[1];
    var _k = useState(""), message = _k[0], setMessage = _k[1];
    var _j = useState({
      workspace_mode: "registered", project_id: "", controller_profile: "", unregistered_board_slug: "", local_project_id: "", local_board_name: "", pack: "", board_slug: "", goal: "", worker_default: "",
      stage_profiles: {}, constraint_kind: "none", constraints_content: "",
      constraints_skill: "", constraints_skill_digest: "", workflow_id: "",
      board_draft: "", board_name: ""
    }), form = _j[0], setForm = _j[1];

    useEffect(function () {
      var cancelled = false;
      buildWizardInventory().then(function (next) {
        if (cancelled) return;
        setInventory(next);
        var saved = {};
        try {
          saved = JSON.parse(window.localStorage.getItem(
            "daidala:start-default:v1:" + (next.controller_profile || "unknown")
          ) || "{}");
        } catch (_error) {}
        setForm(function (current) {
          var profiles = Array.isArray(next.profiles) ? next.profiles : [];
          var packOptions = Array.isArray(next.pack_options) ? next.pack_options : [];
          var packNames = packOptions.map(function (option) { return option.name; });
          var projects = Array.isArray(next.projects) ? next.projects : [];
          var boards = Array.isArray(next.boards) ? next.boards : [];
          var worker = profiles.indexOf(saved.worker_default) >= 0
            ? saved.worker_default
            : profiles.indexOf("default") >= 0 ? "default" : "";
          var stages = {};
          WIZARD_STAGES.forEach(function (stage) {
            stages[stage] = profiles.indexOf(saved.stage_profiles && saved.stage_profiles[stage]) >= 0
              ? saved.stage_profiles[stage]
              : worker;
          });
          var selectedProject = projects.find(function (row) {
            return row.project_id === (saved.project_id || current.project_id) &&
              row.controller_profile === (saved.controller_profile || current.controller_profile);
          }) || projects.find(function (row) {
            return row.project_id === (saved.project_id || current.project_id);
          }) || (projects.length === 1 ? projects[0] : null);
          return Object.assign({}, current, {
            project_id: selectedProject ? selectedProject.project_id : "",
            controller_profile: selectedProject ? selectedProject.controller_profile : "",
            pack: packNames.indexOf(saved.pack || current.pack) >= 0
              ? (saved.pack || current.pack) : packNames[0] || "",
            board_slug: boards.some(function (row) {
              return row.slug === (saved.board_slug || current.board_slug);
            }) ? (saved.board_slug || current.board_slug) : "",
            worker_default: worker,
            stage_profiles: stages
          });
        });
      }).catch(function (reason) {
        if (!cancelled) setError("Could not load the Start workflow inventory: " + errorText(reason));
      });
      return function () { cancelled = true; };
    }, [reload]);

    useEffect(function () {
      var awaitingReturn = false;
      function refreshReturnedInventory() {
        var query = new URLSearchParams(window.location.search);
        if (query.get("return") === "start-workflow") {
          awaitingReturn = true;
        } else if (awaitingReturn) {
          awaitingReturn = false;
          setReload(function (value) { return value + 1; });
        }
      }
      window.addEventListener("popstate", refreshReturnedInventory);
      return function () { window.removeEventListener("popstate", refreshReturnedInventory); };
    }, []);

    useEffect(function () {
      if (!props.returnedSource) return;
      setForm(function (current) {
        return Object.assign({}, current, {
          constraint_kind: "skill",
          constraints_skill: props.returnedSource.name,
          constraints_skill_digest: props.returnedSource.digest
        });
      });
      setReadiness(null); setPreview(null); setConfirmed(false); setError("");
      setMessage("Selected policy source returned to this browser-only Start draft. Review and preview it before starting.");
      props.onSourceApplied();
    }, [props.returnedSource]);

    function change(field, value) {
      setForm(function (current) {
        return Object.assign({}, current, (function () { var patch = {}; patch[field] = value; return patch; })());
      });
      setReadiness(null);
      setPreview(null);
      setConfirmed(false);
      setError("");
      setMessage("");
    }

    function changeWorker(value) {
      var stages = {};
      WIZARD_STAGES.forEach(function (stage) { stages[stage] = value; });
      setForm(function (current) {
        return Object.assign({}, current, { worker_default: value, stage_profiles: stages });
      });
      setReadiness(null); setPreview(null); setConfirmed(false);
    }

    function changeStage(stage, value) {
      var stages = Object.assign({}, form.stage_profiles); stages[stage] = value;
      change("stage_profiles", stages);
    }

    function changePolicySource(value) {
      var sources = inventory && Array.isArray(inventory.policy_sources)
        ? inventory.policy_sources : [];
      var selected = sources.find(function (source) { return source.name === value; });
      setForm(function (current) {
        return Object.assign({}, current, {
          constraints_skill: selected ? selected.name : "",
          constraints_skill_digest: selected ? selected.digest : ""
        });
      });
      setReadiness(null); setPreview(null); setConfirmed(false); setError(""); setMessage("");
    }

    function envelope() {
      var request = {
        goal: form.goal,
        pack: form.pack,
        stage_profiles: form.stage_profiles
      };

      if (form.workflow_id.trim()) request.workflow_id = form.workflow_id.trim();
      if (form.constraint_kind === "content") request.constraints_content = form.constraints_content;
      if (form.constraint_kind === "skill") {
        request.constraints_skill = form.constraints_skill;
        request.constraints_skill_digest = form.constraints_skill_digest;
      }
      if (form.workspace_mode === "local") {
        return { project_id: form.local_project_id, board_name: form.local_board_name, request: request };
      }
      if (form.workspace_mode === "unregistered") {
        return { selection: { mode: "unregistered", board_slug: form.unregistered_board_slug }, request: request };
      }
      return { selection: { mode: "registered", project_id: form.project_id, controller_profile: form.controller_profile }, request: request };
    }

    function runReadiness() {
      var identityError = workflowIdentityError(form.workflow_id);
      if (identityError) {
        setError(identityError); setReadiness(null); setPreview(null); setConfirmed(false);
        return;
      }
      setBusy(true); setError("");
      if (form.workspace_mode === "local") {
        setReadiness({
          ready: false,
          checks: [{
            id: "local-project-pending",
            passed: false,
            detail: "Local project readiness is validated after its confirmed initialization."
          }]
        });
        setPreview(null); setConfirmed(false); setBusy(false);
        return;
      }
      wizardReadiness(envelope()).then(function (result) {
        setReadiness(result.readiness || result); setPreview(null); setConfirmed(false);
      }).catch(function (reason) {
        setReadiness(null); setError("Readiness could not be checked: " + errorText(reason));
      }).finally(function () { setBusy(false); });
    }

    function runPreview() {
      var identityError = workflowIdentityError(form.workflow_id);
      if (identityError) {
        setError(identityError); setReadiness(null); setPreview(null); setConfirmed(false);
        return;
      }
      setBusy(true); setError("");
      (form.workspace_mode === "local" ? wizardLocalPreview : wizardPreview)(envelope()).then(function (result) {
        setReadiness(result.readiness || null); setPreview(result); setConfirmed(false);
      }).catch(function (reason) {
        setPreview(null); setError("Preview could not be created: " + errorText(reason));
      }).finally(function () { setBusy(false); });
    }

    function runStart() {
      if (!preview || !confirmed) return;
      setBusy(true); setError("");
      (form.workspace_mode === "local" ? wizardLocalStart : wizardStart)(Object.assign({}, envelope(), {
        preview_digest: preview.preview_digest, confirm: true
      })).then(function (result) {
        props.onStarted(result.workflow.workflow_id);
      }).catch(function (reason) {
        var workflowId = existingWorkflowId(reason);
        if (workflowId) {
          props.onExisting(workflowId);
          return;
        }
        setError("Workflow was not started: " + errorText(reason));
      }).finally(function () { setBusy(false); });
    }

    function saveDefault() {
      if (!inventory) return;
      try {
        window.localStorage.setItem("daidala:start-default:v1:" + inventory.controller_profile,
          JSON.stringify({
            project_id: form.project_id, controller_profile: form.controller_profile, pack: form.pack, board_slug: form.board_slug,
            worker_default: form.worker_default, stage_profiles: form.stage_profiles
          })
        );
        setMessage("Default saved in this browser for the mounted profile.");
      } catch (_error) { setError("This browser could not save the default."); }
    }

    function previewBoard() {
      setBusy(true); setError("");
      wizardBoardPreview({ slug: form.board_draft, name: form.board_name || null }).then(function (result) {
        setBoardPreview(result); setBoardConfirmed(false);
      }).catch(function (reason) {
        setBoardPreview(null); setError("Board preview could not be created: " + errorText(reason));
      }).finally(function () { setBusy(false); });
    }

    function createBoard() {
      if (!boardPreview || !boardConfirmed) return;
      setBusy(true); setError("");
      wizardCreateBoard({ slug: form.board_draft, name: form.board_name || null,
        preview_digest: boardPreview.preview_digest, confirm: true }).then(function () {
        setForm(function (current) {
          return Object.assign({}, current, { board_slug: current.board_draft, board_draft: "", board_name: "" });
        });
        setBoardPreview(null); setBoardConfirmed(false); setReload(function (value) { return value + 1; });
      }).catch(function (reason) {
        setError("Board was not created: " + errorText(reason));
      }).finally(function () { setBusy(false); });
    }

    function select(label, value, onChange, choices, disabled) {
      return createElement("label", { className: "daidala-wizard-field" },
        createElement("span", null, label),
        createElement("select", { value: value, disabled: !!disabled, onChange: function (event) { onChange(event.target.value); } },
          createElement("option", { value: "" }, "Select…"),
          choices.map(function (choice) { return createElement("option", { key: choice.value, value: choice.value }, choice.label); })
        )
      );
    }

    var profiles = inventory && Array.isArray(inventory.profiles) ? inventory.profiles : [];
    var projects = inventory && Array.isArray(inventory.projects) ? inventory.projects : [];
    var ineligible = inventory && Array.isArray(inventory.ineligible_repositories) ? inventory.ineligible_repositories : [];
    var boards = inventory && Array.isArray(inventory.boards) ? inventory.boards : [];
    var packs = inventory && Array.isArray(inventory.pack_options) ? inventory.pack_options : [];
    var policySources = inventory && Array.isArray(inventory.policy_sources) ? inventory.policy_sources : [];
    var selectedRepository = projects.find(function (row) {
      return row.project_id === form.project_id && row.controller_profile === form.controller_profile;
    }) || null;
    var selectedUnregistered = ((inventory && inventory.unregistered_boards) || []).find(function (row) {
      return row.slug === form.unregistered_board_slug;
    }) || null;
    var localWorkdir = inventory && inventory.checkouts_root && form.local_project_id
      ? inventory.checkouts_root + "/" + form.local_project_id : "";
    var selectedPack = packs.find(function (option) { return option.name === form.pack; }) || null;
    var workflowIdError = workflowIdentityError(form.workflow_id);
    var hasRequest = selectedPack && selectedPack.status === "ready" &&
      form.pack && form.goal.trim() &&
      (form.workspace_mode === "local"
        ? form.local_project_id && form.local_board_name.trim()
        : form.workspace_mode === "unregistered" ? form.unregistered_board_slug : form.project_id) &&
      WIZARD_STAGES.every(function (stage) { return form.stage_profiles[stage]; }) &&
      !workflowIdError;

    return createElement("section", { className: "daidala-wizard", "data-testid": "daidala-start-workflow" },
      createElement("header", { className: "daidala-wizard-header" },
        createElement("div", null,
          createElement("button", { type: "button", className: "daidala-back", onClick: props.onClose }, "← Back to workflows"),
          createElement("h2", null, "Start workflow"),
          createElement("p", null, "Profile-scoped first-workflow setup. Preview before any mutation.")
        ),
        createElement("a", { href: "/cron", className: "daidala-cron-link" }, "Open Hermes Cron")
      ),
      !inventory ? createElement("p", { className: "daidala-state daidala-state-loading" }, "Loading setup inventory") : null,
      inventory ? createElement("div", { className: "daidala-wizard-layout" },
        createElement("form", { className: "daidala-wizard-form", onSubmit: function (event) { event.preventDefault(); runPreview(); } },
          createElement("section", { className: "daidala-wizard-section" },
            createElement("h3", null, "Mounted controller profile"),
            createElement("p", { className: "daidala-workflow-meta" }, inventory.controller_profile || "Unavailable")
          ),
          createElement("div", { className: "daidala-wizard-section-heading" },
            select("Pack · readiness", form.pack, function (value) { change("pack", value); }, packs.map(function (option) { return { value: option.name, label: option.name + " · " + option.status }; })),
            createElement("a", { href: "/daidala?section=packs&return=start-workflow", onClick: function (event) { navigateDashboard(event, "/daidala?section=packs&return=start-workflow"); } }, "Manage packs")
          ),
          selectedPack ? createElement("p", {
            className: selectedPack.status === "ready"
              ? "daidala-banner daidala-banner-success"
              : "daidala-banner daidala-banner-warning"
          },
            selectedPack.status === "ready"
              ? selectedPack.name + " is installed and ready."
              : selectedPack.status === "installation required"
                ? selectedPack.name + " requires external skill installation before a workflow can start. Use Manage packs to review and install them."
                : selectedPack.status === "readiness unavailable"
                  ? selectedPack.name + " readiness could not be verified. Use Manage packs to retry the check."
                  : selectedPack.name + " is blocked. Use Manage packs to inspect the blockers."
          ) : null,
          createElement("section", { className: "daidala-wizard-section" },
            createElement("h3", null, "Workspace"),
            createElement("label", null, createElement("input", { type: "radio", checked: form.workspace_mode === "registered", onChange: function () { change("workspace_mode", "registered"); } }), " Registered GitHub repository"),
            createElement("label", null, createElement("input", { type: "radio", checked: form.workspace_mode === "unregistered", onChange: function () { change("workspace_mode", "unregistered"); } }), " Existing unregistered repository"),
            createElement("label", null, createElement("input", { type: "radio", checked: form.workspace_mode === "local", onChange: function () { change("workspace_mode", "local"); } }), " Initialize local project"),
            form.workspace_mode === "registered" ? createElement("div", null,
            createElement("div", { className: "daidala-wizard-section-heading" },
              select("Registered repository (<repo> · <board> · <profile>)", form.controller_profile && form.project_id ? form.controller_profile + ":" + form.project_id : "", function (value) { var separator = value.indexOf(":"); setForm(function (current) { return Object.assign({}, current, { controller_profile: separator > 0 ? value.slice(0, separator) : "", project_id: separator > 0 ? value.slice(separator + 1) : "" }); }); }, projects.map(function (row) { return { value: row.controller_profile + ":" + row.project_id, label: row.repository + " · " + row.board + " · " + row.controller_profile }; })),
              createElement("a", { href: "/daidala?section=repositories&return=start-workflow", onClick: function (event) { navigateDashboard(event, "/daidala?section=repositories&return=start-workflow"); } }, "Register GitHub Repository"),
              selectedRepository && selectedRepository.workdir ? createElement("p", { className: "daidala-workflow-meta" }, "Working directory: " + selectedRepository.workdir) : null
            ),
            createElement("p", { className: "daidala-workflow-meta" }, projects.length ? "The selected GitHub repository supplies its board. Register repositories in Config → GitHub Repositories." : ineligible.length ? "Registered GitHub repositories exist but none are selectable." : "No GitHub repository is registered in this Hermes installation. Use Register GitHub Repository."),
              ineligible.length ? createElement("section", { className: "daidala-wizard-section", "data-testid": "daidala-ineligible-repositories" },
                createElement("h4", null, "Not selectable"),
                ineligible.map(function (row) {
                  return createElement("article", { key: row.controller_profile + ":" + row.project_id },
                    createElement("p", null, row.repository + " · " + row.board + " · " + row.controller_profile),
                    createElement("p", { className: "daidala-workflow-meta" }, "Reason: " + row.detail),
                    createElement("p", { className: "daidala-workflow-meta" }, "Conclusion: " + row.conclusion),
                    row.workdir ? createElement("p", { className: "daidala-workflow-meta" }, "Working directory: " + row.workdir) : null
                  );
                })
              ) : null
            ) : form.workspace_mode === "unregistered" ? createElement("div", { className: "daidala-wizard-pair" },
              select("Unregistered board", form.unregistered_board_slug, function (value) { change("unregistered_board_slug", value); }, (inventory.unregistered_boards || []).map(function (row) { return { value: row.slug, label: row.name + " · " + row.slug }; })),
              createElement("p", { className: "daidala-workflow-meta" }, "Only unbound boards with a clean local Git root are listed. Configure a board workdir in Hermes if this list is empty."),
              selectedUnregistered && selectedUnregistered.workdir ? createElement("p", { className: "daidala-workflow-meta" }, "Working directory: " + selectedUnregistered.workdir) : null
            ) : createElement("div", { className: "daidala-wizard-pair" },
              createElement("label", { className: "daidala-wizard-field" }, createElement("span", null, "Project slug"), createElement("input", { value: form.local_project_id, onChange: function (event) { change("local_project_id", event.target.value); } })),
              createElement("label", { className: "daidala-wizard-field" }, createElement("span", null, "Board display name"), createElement("input", { value: form.local_board_name, onChange: function (event) { change("local_board_name", event.target.value); } })),
              createElement("p", { className: "daidala-workflow-meta" }, "Creates a local Git repository, default policy, initial commit, and unbound board. No GitHub repository is created."),
              localWorkdir ? createElement("p", { className: "daidala-workflow-meta" }, "Working directory: " + localWorkdir) : null
            )
          ),
          createElement("label", { className: "daidala-wizard-field" }, createElement("span", null, "Requested outcome / Prompt"),
            createElement("textarea", { value: form.goal, rows: 3, onChange: function (event) { change("goal", event.target.value); } })
          ),
          select("Worker profile default", form.worker_default, changeWorker, profiles.map(function (name) { return { value: name, label: name }; })),
          createElement("p", { className: "daidala-workflow-meta" }, "The repository <profile> owns the registration and supplies its board and checkout. Worker profile default assigns who runs every stage. They do not have to match, and Start will not rewrite either. Later stages fail if those workers cannot use the working directory."),
          (function () {
            var gateways = inventory && Array.isArray(inventory.worker_gateways) ? inventory.worker_gateways : [];
            var selected = gateways.filter(function (row) { return row.profile === form.worker_default; })[0];
            return selected && selected.status !== "running"
              ? createElement("p", { className: "daidala-banner daidala-banner-error" }, "Worker gateway is not running for " + form.worker_default + ". Start it with hermes -p " + form.worker_default + " gateway start before Ready cards will dispatch.")
              : null;
          })(),
          form.workspace_mode === "registered" && selectedRepository && form.worker_default && selectedRepository.controller_profile !== form.worker_default
            ? createElement("p", { className: "daidala-workflow-meta" }, "This repository is owned by " + selectedRepository.controller_profile + ". Workers are " + form.worker_default + ".")
            : null,
          createElement("details", { className: "daidala-wizard-advanced" },
            createElement("summary", null, "Advanced workflow settings"),
            WIZARD_STAGES.map(function (stage) {
              return select(stage.charAt(0).toUpperCase() + stage.slice(1), form.stage_profiles[stage] || "", function (value) { changeStage(stage, value); }, profiles.map(function (name) { return { value: name, label: name }; }));
            }),
            createElement("label", { className: "daidala-wizard-field" }, createElement("span", null, "Workflow identity (optional)"),
              createElement("input", {
                value: form.workflow_id,
                "aria-describedby": workflowIdError ? "daidala-workflow-identity-error" : undefined,
                "aria-invalid": !!workflowIdError,
                onChange: function (event) { change("workflow_id", event.target.value); }
              }),
              workflowIdError ? createElement("p", {
                id: "daidala-workflow-identity-error",
                role: "alert",
                className: "daidala-banner daidala-banner-error"
              }, workflowIdError) : null
            )
          ),
          createElement("section", { className: "daidala-wizard-section" },
            createElement("div", { className: "daidala-wizard-section-heading" }, createElement("h3", null, "Workflow constraints"), createElement("a", { href: "/daidala?section=constraints&return=start-workflow", onClick: function (event) { navigateDashboard(event, "/daidala?section=constraints&return=start-workflow"); } }, "Manage sources")),
            createElement("div", { className: "daidala-constraint-tabs", role: "tablist", "aria-label": "Constraint source" },
              [{ value: "content", label: "Write YAML" }, { value: "skill", label: "Reference skill" }, { value: "none", label: "No constraints" }].map(function (choice) {
                return createElement("button", { key: choice.value, type: "button", role: "tab", "aria-selected": form.constraint_kind === choice.value, className: form.constraint_kind === choice.value ? "is-selected" : "", onClick: function () { change("constraint_kind", choice.value); } }, choice.label);
              })
            ),
            form.constraint_kind === "content" ? createElement("textarea", { value: form.constraints_content, rows: 4, placeholder: "Draft constraints stay in browser memory until preview.", onChange: function (event) { change("constraints_content", event.target.value); } }) : null,
            form.constraint_kind === "skill" ? createElement("div", { className: "daidala-wizard-pair" },
              select("Installed policy source", form.constraints_skill, changePolicySource, policySources.map(function (source) { return { value: source.name, label: source.name }; })),
              createElement("p", { className: "daidala-workflow-meta" }, form.constraints_skill_digest ? "Exact digest " + form.constraints_skill_digest : "Select an installed policy source.")
            ) : null
          ),
          createElement("button", { type: "button", disabled: !hasRequest || busy, onClick: saveDefault }, "Save as default")
        ),
        createElement("aside", { className: "daidala-readiness", "data-testid": "daidala-start-readiness" },
          createElement("h3", null, "Start readiness"),
          readiness ? createElement("ul", null, (readiness.checks || []).map(function (check) {
            return createElement("li", { key: check.id, className: check.passed ? "is-ready" : "is-blocked" },
              (check.passed ? "✓ " : "× ") + check.id + (check.detail ? " — " + check.detail : ""));
          })) : createElement("p", null, "Check readiness before preview. The result is informative and does not block preview."),
          readiness && readiness.ready === false
            ? createElement("p", { className: "daidala-workflow-meta" }, "Readiness is informative. Preview stays available after this check. Start still requires a passing start gate.")
            : null,
          createElement("div", { className: "daidala-wizard-actions" },
            createElement("button", { type: "button", disabled: !hasRequest || busy, onClick: runReadiness }, "Check readiness"),
            createElement("button", { type: "button", disabled: !hasRequest || busy || !readiness, onClick: runPreview }, "Preview workflow")
          )
        )
      ) : null,
      preview ? createElement("section", { className: "daidala-wizard-preview" },
        createElement("h3", null, "Preview result · non-mutating"),
        createElement("p", null, "Digest " + preview.preview_digest),
        createElement("label", null, createElement("input", { type: "checkbox", checked: confirmed, onChange: function (event) { setConfirmed(event.target.checked); } }), " I confirm applying this exact preview"),
        createElement("button", { type: "button", disabled: busy || !confirmed, onClick: runStart }, "Start now")
      ) : null,
      createElement("p", { className: "daidala-workflow-meta" }, "Hermes Cron schedules future admissions only. Pausing Cron does not pause active workflow cards."),
      message ? createElement("p", { role: "status" }, message) : null,
      error ? createElement("p", { role: "status", className: "daidala-banner daidala-banner-error" }, error) : null
    );
  }

  function ArtifactsPanel() {
    var artifactsState = useVisiblePolling(POLL_MS, function () { return buildArtifacts(null); });
    var curatorState = useVisiblePolling(POLL_MS, buildCuratorStatus);
    var selectedState = useState(null), selectedId = selectedState[0], setSelectedId = selectedState[1];
    var textState = useState(null), text = textState[0], setText = textState[1];
    var textErrorState = useState(""), textError = textErrorState[0], setTextError = textErrorState[1];
    var filterState = useState({ workflow: "", kind: "", stage: "", availability: "", after: "", search: "" });
    var filters = filterState[0], setFilters = filterState[1];
    var previewState = useState(null), curatorPreview = previewState[0], setCuratorPreview = previewState[1];
    var confirmedState = useState(false), curatorConfirmed = confirmedState[0], setCuratorConfirmed = confirmedState[1];
    var busyState = useState(false), busy = busyState[0], setBusy = busyState[1];
    var messageState = useState(""), message = messageState[0], setMessage = messageState[1];
    var errorState = useState(""), error = errorState[0], setError = errorState[1];
    var artifacts = Array.isArray(artifactsState.snapshot) ? artifactsState.snapshot : [];
    var curator = curatorState.snapshot || null;

    function changeFilter(name, value) {
      setFilters(function (current) {
        var next = Object.assign({}, current);
        next[name] = value;
        return next;
      });
    }

    var workflows = Array.from(new Set(artifacts.map(function (row) { return row.workflow_id; }))).sort();
    var kinds = Array.from(new Set(artifacts.map(function (row) { return row.kind; }))).sort();
    var stages = Array.from(new Set(artifacts.map(function (row) { return row.stage; }).filter(Boolean))).sort();
    var filtered = artifacts.filter(function (row) {
      var haystack = [row.workflow_id, row.kind, row.stage, row.artifact_id, row.digest]
        .filter(Boolean).join(" ").toLowerCase();
      return (!filters.workflow || row.workflow_id === filters.workflow) &&
        (!filters.kind || row.kind === filters.kind) &&
        (!filters.stage || row.stage === filters.stage) &&
        (!filters.availability || row.availability === filters.availability) &&
        (!filters.after || (row.recorded_at && row.recorded_at.slice(0, 10) >= filters.after)) &&
        (!filters.search || haystack.indexOf(filters.search.toLowerCase()) >= 0);
    });
    var selected = artifacts.find(function (row) { return row.artifact_id === selectedId; }) || null;
    var curatorRows = curator && Array.isArray(curator.rows) ? curator.rows : [];
    var curatorRow = selected
      ? curatorRows.find(function (row) { return row.workflow_id === selected.workflow_id; }) || null
      : null;
    var archiveIds = curatorRow && Array.isArray(curatorRow.archive_ids) ? curatorRow.archive_ids : [];
    var latestArchiveId = archiveIds.length ? archiveIds[archiveIds.length - 1] : null;

    useEffect(function () {
      setText(null);
      setTextError("");
      setCuratorPreview(null);
      setCuratorConfirmed(false);
      if (!selected) return;
      buildArtifactText(selected.workflow_id, selected.artifact_id)
        .then(setText)
        .catch(function (reason) { setTextError(errorText(reason)); });
    }, [selectedId]);

    function refresh() {
      artifactsState.refresh();
      curatorState.refresh();
    }

    function runDownload() {
      if (!selected) return;
      setBusy(true); setError(""); setMessage("");
      downloadArtifact(selected)
        .then(function () { setMessage("Verified artifact download started."); })
        .catch(function (reason) { setError("Artifact download failed: " + errorText(reason)); })
        .finally(function () { setBusy(false); });
    }

    function runCuratorPreview(operation, archiveId) {
      if (!selected) return;
      setBusy(true); setError(""); setMessage(""); setCuratorConfirmed(false);
      previewCurator(selected.workflow_id, operation, archiveId)
        .then(setCuratorPreview)
        .catch(function (reason) { setError("Curator preview failed: " + errorText(reason)); })
        .finally(function () { setBusy(false); });
    }

    function runCuratorApply() {
      if (!selected || !curatorPreview || !curatorConfirmed) return;
      setBusy(true); setError(""); setMessage("");
      applyCurator(selected.workflow_id, curatorPreview)
        .then(function (result) {
          setMessage("Curator operation applied: " + result.operation + ".");
          setCuratorPreview(null); setCuratorConfirmed(false); refresh();
        })
        .catch(function (reason) { setError("Curator operation failed: " + errorText(reason)); })
        .finally(function () { setBusy(false); });
    }

    function selector(label, name, values) {
      return createElement("label", { className: "daidala-artifact-filter" },
        createElement("span", null, label),
        createElement("select", { value: filters[name], onChange: function (event) { changeFilter(name, event.target.value); } },
          createElement("option", { value: "" }, "All"),
          values.map(function (value) { return createElement("option", { key: value, value: value }, value); })
        )
      );
    }

    var counts = curator && curator.counts ? curator.counts : { active: 0, stale: 0, archived: 0 };
    return createElement("section", { className: "daidala-artifacts", "data-testid": "daidala-artifacts" },
      createElement("header", { className: "daidala-artifact-heading" },
        createElement("div", null,
          createElement("h2", null, "Artifacts"),
          createElement("p", { className: "daidala-workflow-meta" }, "Ledger-bound metadata, literal preview, verified download, and curator state.")
        ),
        createElement("button", { type: "button", className: "daidala-refresh", onClick: refresh }, "Refresh artifacts")
      ),
      createElement("section", { className: "daidala-curator-summary", "data-testid": "daidala-curator-summary" },
        createElement("strong", null, "Curator " + (curator && curator.policy && curator.policy.enabled ? "enabled" : "disabled")),
        createElement("span", null, "Active " + (counts.active || 0)),
        createElement("span", null, "Stale " + (counts.stale || 0)),
        createElement("span", null, "Archived " + (counts.archived || 0)),
        createElement("span", null, "Pinned " + (curator && curator.pinned || 0))
      ),
      createElement("div", { className: "daidala-artifact-filters" },
        selector("Workflow", "workflow", workflows),
        selector("Kind", "kind", kinds),
        selector("Stage", "stage", stages),
        selector("Availability", "availability", ["active", "archived", "active-and-archived", "missing"]),
        createElement("label", { className: "daidala-artifact-filter" }, createElement("span", null, "Recorded after"),
          createElement("input", { type: "date", value: filters.after, onChange: function (event) { changeFilter("after", event.target.value); } })
        ),
        createElement("label", { className: "daidala-artifact-filter" }, createElement("span", null, "Search"),
          createElement("input", { type: "search", value: filters.search, onChange: function (event) { changeFilter("search", event.target.value); } })
        )
      ),
      artifactsState.loading && !artifacts.length
        ? createElement("p", { className: "daidala-state daidala-state-loading" }, "Loading artifacts")
        : artifactsState.snapshot === null
          ? createElement("p", { className: "daidala-state daidala-state-unavailable" }, "Artifact catalog unavailable")
          : createElement("div", { className: "daidala-artifact-layout" },
              createElement("div", { className: "daidala-artifact-list", role: "list" },
                filtered.length ? filtered.map(function (row) {
                  return createElement("div", { key: row.artifact_id, role: "listitem" },
                    createElement("button", {
                      type: "button",
                      className: "daidala-artifact-row" + (selectedId === row.artifact_id ? " is-selected" : ""),
                      onClick: function () { setSelectedId(row.artifact_id); }
                    },
                      createElement("strong", null, (row.stage || row.kind) + " · r" + row.plan_revision),
                      createElement("span", null, row.workflow_id),
                      createElement("span", null, row.availability + " · " + (row.size === null ? "size unavailable" : row.size + " bytes")),
                      createElement("code", null, row.digest.slice(0, 16) + "…")
                    )
                  );
                }) : createElement("p", { className: "daidala-state daidala-state-empty" }, "No artifacts match these filters")
              ),
              createElement("article", { className: "daidala-artifact-detail", "data-testid": "daidala-artifact-detail" },
                !selected ? createElement("p", { className: "daidala-state daidala-state-empty" }, "Select an artifact to review it") : createElement(React.Fragment, null,
                  createElement("h3", null, (selected.stage || selected.kind) + " artifact"),
                  createElement("dl", { className: "daidala-artifact-identity" },
                    createElement("dt", null, "Workflow"), createElement("dd", null, selected.workflow_id),
                    createElement("dt", null, "Artifact ID"), createElement("dd", null, selected.artifact_id),
                    createElement("dt", null, "SHA-256"), createElement("dd", null, selected.digest),
                    createElement("dt", null, "Recorded"), createElement("dd", null, selected.recorded_at || "Unavailable"),
                    createElement("dt", null, "State"), createElement("dd", null, selected.availability)
                  ),
                  createElement("div", { className: "daidala-artifact-actions" },
                    createElement("button", { type: "button", disabled: busy, onClick: runDownload }, "Download verified bytes"),
                    createElement("button", { type: "button", disabled: busy, onClick: function () { runCuratorPreview(curatorRow && curatorRow.pinned ? "unpin" : "pin", null); } }, curatorRow && curatorRow.pinned ? "Preview unpin" : "Preview pin"),
                    createElement("button", { type: "button", disabled: busy || selected.availability === "archived", onClick: function () { runCuratorPreview("archive", null); } }, "Preview archive"),
                    createElement("button", { type: "button", disabled: busy || !latestArchiveId, onClick: function () { runCuratorPreview("restore", latestArchiveId); } }, "Preview restore")
                  ),
                  curatorRow ? createElement("p", { className: "daidala-workflow-meta" },
                    "Curator state " + curatorRow.state + (curatorRow.pinned ? " · pinned" : "") +
                    (curatorRow.next_transition_at ? " · next transition " + curatorRow.next_transition_at : "")
                  ) : null,
                  curatorPreview ? createElement("section", { className: "daidala-artifact-curator-preview", "data-testid": "daidala-curator-preview" },
                    createElement("h4", null, "Curator preview · " + curatorPreview.operation),
                    createElement("p", null, (curatorPreview.actions || []).length + " transition(s) · digest " + curatorPreview.preview_digest),
                    createElement("label", null, createElement("input", { type: "checkbox", checked: curatorConfirmed, onChange: function (event) { setCuratorConfirmed(event.target.checked); } }), " I confirm applying this exact curator preview"),
                    createElement("button", { type: "button", disabled: busy || !curatorConfirmed, onClick: runCuratorApply }, "Apply curator operation")
                  ) : null,
                  createElement("section", { className: "daidala-artifact-preview", "data-testid": "daidala-artifact-literal-preview" },
                    createElement("h4", null, "Literal text preview"),
                    text ? createElement("pre", null, text.content) : textError
                      ? createElement("p", { className: "daidala-banner daidala-banner-warning" }, "Literal preview unavailable. Use verified download. " + textError)
                      : createElement("p", { className: "daidala-state daidala-state-loading" }, "Loading literal preview")
                  )
                )
              )
            ),
      message ? createElement("p", { role: "status", className: "daidala-banner" }, message) : null,
      error ? createElement("p", { role: "status", className: "daidala-banner daidala-banner-error" }, error) : null
    );
  }

  function Page() {
    var health = useVisiblePolling(POLL_MS, buildHealth);
    var workflowsState = useVisiblePolling(POLL_MS, buildWorkflows);
    var dispatcherState = useState(null);
    var dispatcher = dispatcherState[0];
    var setDispatcher = dispatcherState[1];
    var initialRoute = dashboardRoute();
    var _a = useState(false), starting = _a[0], setStarting = _a[1];
    var _b = useState(initialRoute.workflowId), openWorkflowId = _b[0], setOpenWorkflowId = _b[1];
    var _c = useState(""), startNotice = _c[0], setStartNotice = _c[1];
    var _d = useState(initialRoute), route = _d[0], setRoute = _d[1];
    var _e = useState(false), showArchived = _e[0], setShowArchived = _e[1];
    var returnedSourceState = useState(null), returnedSource = returnedSourceState[0], setReturnedSource = returnedSourceState[1];

    useEffect(function () {
      var cancelled = false;
      buildDispatcherReadiness().then(function (value) {
        if (!cancelled) setDispatcher(value);
      }).catch(function () {
        if (!cancelled) setDispatcher(null);
      });
      return function () { cancelled = true; };
    }, []);

    useEffect(function () {
      function syncRoute() {
        var nextRoute = dashboardRoute();
        setRoute(nextRoute);
        setOpenWorkflowId(nextRoute.workflowId);
      }
      window.addEventListener("popstate", syncRoute);
      return function () { window.removeEventListener("popstate", syncRoute); };
    }, []);

    var workflowIds = useMemo(
      function () {
        if (!Array.isArray(workflowsState.snapshot)) return [];
        return workflowsState.snapshot.map(function (row) {
          return row.workflow_id;
        });
      },
      [workflowsState.snapshot]
    );

    function refreshAll() {
      health.refresh();
      workflowsState.refresh();
      buildDispatcherReadiness().then(setDispatcher).catch(function () {
        setDispatcher(null);
      });
    }

    function returnSourceToStart(source) {
      setReturnedSource(source);
      window.history.pushState({}, "", "/daidala?return=start-workflow");
      window.dispatchEvent(new PopStateEvent("popstate"));
    }

    function resumeExistingWorkflow(workflowId) {
      window.history.pushState({}, "", "/daidala?workflow=" + encodeURIComponent(workflowId));
      window.dispatchEvent(new PopStateEvent("popstate"));
      setStarting(false);
      setStartNotice("Opened the existing workflow and resumed read-only polling.");
      workflowsState.refresh();
    }

    var detailStates = {};
    for (var i = 0; i < workflowIds.length; i += 1) {
      var id = workflowIds[i];
      // useVisiblePolling must be called at the top level, so we cannot
      // actually iterate here. Instead, we lazily load details through
      // a sub-render. See WorkflowDetail below.
    }

    var workflows = Array.isArray(workflowsState.snapshot)
      ? workflowsState.snapshot
      : [];
    var archivedWorkflows = workflows.filter(function (row) {
      return row.lifecycle_status === "archived";
    });
    var visibleWorkflows = showArchived
      ? workflows
      : workflows.filter(function (row) { return row.lifecycle_status !== "archived"; });
    var listedWorkflows = openWorkflowId
      ? visibleWorkflows.filter(function (row) { return row.workflow_id !== openWorkflowId; })
      : visibleWorkflows;
    var firstLoad = workflowsState.loading && visibleWorkflows.length === 0;
    var hostDown = workflowsState.snapshot === null;
    var healthDown = health.snapshot && health.snapshot.success === false;
    var blockedGateways = dispatcher && Array.isArray(dispatcher.blocked_profiles)
      ? dispatcher.blocked_profiles
      : [];
    var assigneeMismatches = dispatcher && Array.isArray(dispatcher.assignee_mismatches)
      ? dispatcher.assignee_mismatches
      : [];
    var firstMismatch = assigneeMismatches[0];
    var mismatchNext = firstMismatch
      ? "Cannot record required skill activation: the active card is assigned to "
        + firstMismatch.assignee + " but the workflow binds " + firstMismatch.stage
        + " to " + firstMismatch.bound_profile
        + ". Align the card assignee/stage profile and retry."
      : "";
    var gatewayNext = blockedGateways.length
      ? "Worker gateway is not running for " + blockedGateways.join(", ")
        + ". Start it with hermes -p <profile> gateway start before Ready cards will dispatch."
      : "";
    var guidance = route.view === "artifacts"
      ? {
        screen: "artifacts",
        title: "Artifact evidence",
        purpose: "Use Artifacts to inspect ledger-bound evidence, read bounded literal previews, and download verified bytes without exposing filesystem paths.",
        next: "If the catalog is empty, no workflow has captured evidence yet. Start or resume a workflow, then return here to review its recorded artifacts."
      }
      : route.view === "config"
        ? {
          screen: "config",
          title: "Configuration readiness",
          purpose: "Use Config to prepare the profile, packs, registered repositories, checkouts, constraints, and verification prerequisites before starting work.",
          next: "Open Verification to identify missing prerequisites, then use the named Config panel to address that specific gap."
        }
        : {
          screen: "workflows",
          title: "Workflow supervision",
          purpose: "Use Workflows to supervise Daidala's approval-gated lifecycle and make the next required human decision from source-bound evidence.",
          next: firstLoad
            ? "Workflow state is loading."
            : hostDown
              ? "Live Kanban state is unavailable. Keep the gateway running, then refresh before acting."
              : mismatchNext
                ? mismatchNext
                : gatewayNext
                  ? gatewayNext
                  : visibleWorkflows.length === 0
                    ? archivedWorkflows.length
                      ? "No active workflow is recorded. Select Show archived workflows to inspect terminal history."
                      : "No workflow is recorded for this profile. Configure prerequisites, then start a workflow when its request is ready."
                    : "Open a workflow to inspect its current evidence and deterministic next action before approving, revising, or reviewing it."
        };

    return createElement(
      "main",
      { className: "daidala-root", "data-testid": "daidala-tab" },
      createElement(
        "header",
        { className: "daidala-root-header" },
        createElement("h1", null, "Daidala"),
        createElement(
          "p",
          { className: "daidala-root-subtitle" },
          "Operator view over the active Daidala profile."
        ),
        createElement("nav", { className: "daidala-primary-nav", "aria-label": "Daidala views" },
          [
            { value: "workflows", label: "Workflows" },
            { value: "artifacts", label: "Artifacts" },
            { value: "config", label: "Config" }
          ].map(function (view) {
            return createElement("button", {
              key: view.value,
              type: "button",
              disabled: starting && view.value !== "workflows",
              title: starting && view.value !== "workflows"
                ? "Finish or close Start workflow before changing views."
                : null,
              className: route.view === view.value ? "is-selected" : "",
              "aria-current": route.view === view.value ? "page" : null,
              onClick: function () {
                window.history.pushState({}, "", "/daidala?view=" + view.value);
                window.dispatchEvent(new PopStateEvent("popstate"));
              }
            }, view.label);
          })
        ),
        route.view === "workflows" ? createElement(
          "button",
          {
            type: "button",
            className: "daidala-refresh",
            "data-testid": "daidala-refresh",
            onClick: refreshAll
          },
          "Refresh"
        ) : null,
        route.view === "workflows" ? createElement("button", {
          type: "button",
          className: "daidala-refresh",
          onClick: function () { setStarting(true); }
        }, "Start workflow") : null,
        route.view === "workflows" && archivedWorkflows.length
          ? createElement("button", {
              type: "button",
              className: "daidala-refresh",
              "aria-pressed": showArchived,
              "data-testid": "daidala-archived-workflow-filter",
              onClick: function () { setShowArchived(!showArchived); }
            }, showArchived
              ? "Hide archived workflows (" + archivedWorkflows.length + ")"
              : "Show archived workflows (" + archivedWorkflows.length + ")")
          : null,
        healthDown
          ? createElement(
              "p",
              { className: "daidala-banner daidala-banner-error" },
              "Daidala backend is unreachable."
            )
          : null
      ),
      createElement(ScreenGuidance, guidance),
      route.view === "workflows" && !starting ? createElement(SetupAdvicePanel) : null,
      starting
        ? createElement(React.Fragment, null,
            route.section ? createElement(ConfigurationPanel, {
              section: route.section,
              returnToStart: route.returnToStart,
              onReturnSource: returnSourceToStart,
              health: health.snapshot,
              onResume: resumeExistingWorkflow
            }) : null,
            createElement(StartWorkflow, {
              onClose: function () { setStarting(false); },
              returnedSource: returnedSource,
              onSourceApplied: function () { setReturnedSource(null); },
              onStarted: function (workflowId) {
                setOpenWorkflowId(workflowId);
                setStartNotice("Workflow started. Keep the gateway running and watch define, then plan.");
                setStarting(false);
                workflowsState.refresh();
              },
              onExisting: function (workflowId) {
                setOpenWorkflowId(workflowId);
                setStartNotice("Workflow already existed. Opened it without creating a second workflow.");
                setStarting(false);
                workflowsState.refresh();
              }
            })
          )
        : route.view === "artifacts"
          ? createElement(ArtifactsPanel)
          : route.view === "config"
            ? createElement(ConfigurationPanel, {
                section: route.section,
                health: health.snapshot,
                onResume: resumeExistingWorkflow
              })
            : createElement(React.Fragment, null,
      openWorkflowId
        ? createElement("section", { className: "daidala-workflows", "data-testid": "daidala-opened-workflow" },
            startNotice ? createElement("p", { role: "status", className: "daidala-banner" }, startNotice) : null,
            createElement(WorkflowDetail, {
              key: openWorkflowId,
              workflow: { workflow_id: openWorkflowId },
              decision: route.workflowId === openWorkflowId ? route.decision : null,
              planRevision: route.workflowId === openWorkflowId ? route.planRevision : null,
              dispatcher: dispatcher
            })
          )
        : null,
      firstLoad
        ? createElement(
            "p",
            { className: "daidala-state daidala-state-loading", "data-testid": "daidala-loading" },
            "Loading workflows"
          )
        : hostDown
          ? createElement(
              "p",
              {
                className: "daidala-state daidala-state-unavailable",
                "data-testid": "daidala-host-unavailable"
              },
              "Live Kanban state unavailable"
            )
          : visibleWorkflows.length === 0
            ? createElement(
                "p",
                {
                  className: "daidala-state daidala-state-empty",
                  "data-testid": "daidala-no-workflows"
                },
                archivedWorkflows.length
                  ? "No active Daidala workflows. Show archived workflows to inspect terminal history."
                  : "No Daidala workflows"
              )
            : createElement(
                "section",
                { className: "daidala-workflows", "data-testid": "daidala-workflows" },
                listedWorkflows.map(function (row) {
                  return createElement(WorkflowDetail, {
                    key: row.workflow_id,
                    workflow: row,
                    dispatcher: dispatcher
                  });
                })
              )
        )
    );
  }

  function WorkflowDetail(props) {
    var workflow = props.workflow;
    var routedPlanRef = useRef(null);
    var detailState = useVisiblePolling(POLL_MS, function () {
      return buildWorkflowDetail(workflow.workflow_id);
    });
    var decisionsState = useVisiblePolling(POLL_MS, function () {
      return buildDecisions(workflow.workflow_id);
    });
    var approvalState = useVisiblePolling(POLL_MS, function () {
      return buildApprovalReview(workflow.workflow_id);
    });
    var reviewState = useVisiblePolling(POLL_MS, function () {
      return buildReviewDecision(workflow.workflow_id);
    });

    useEffect(function () {
      var packet = approvalState.snapshot;
      var revision = packet && packet.tuple ? String(packet.tuple.plan_revision) : null;
      if (
        props.decision !== "plan-approval" ||
        !props.planRevision ||
        revision !== props.planRevision ||
        routedPlanRef.current === props.planRevision
      ) return;
      var panel = document.querySelector('[data-testid="daidala-approval-packet"]');
      if (panel) {
        routedPlanRef.current = props.planRevision;
        panel.scrollIntoView({ block: "start" });
      }
    }, [props.decision, props.planRevision, approvalState.snapshot]);

    return renderWorkflowCard(
      workflow,
      detailState.snapshot,
      decisionsState.snapshot,
      approvalState.snapshot,
      reviewState.snapshot,
      props.dispatcher,
      function () {
        detailState.refresh();
        decisionsState.refresh();
        approvalState.refresh();
        reviewState.refresh();
      },
      function () {
        detailState.refresh();
        decisionsState.refresh();
        approvalState.refresh();
        reviewState.refresh();
      }
    );
  }

  function Slot() {
    var countState = useVisiblePolling(POLL_MS, buildDecisionCount);
    var decisionCount = typeof countState.snapshot === "number"
      ? countState.snapshot
      : 0;
    var hostDown = countState.snapshot === null;

    return createElement(
      "div",
      {
        className: "daidala-slot",
        "data-testid": "daidala-slot",
        title: "Daidala decisions: " + decisionCount
      },
      "Daidala decisions: " + (hostDown ? "?" : String(decisionCount))
    );
  }

  window.__HERMES_PLUGINS__.register(PLUGIN_NAME, Page);
  window.__HERMES_PLUGINS__.registerSlot(PLUGIN_NAME, "sessions:top", Slot);
})();