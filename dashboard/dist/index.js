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
 * artifact-curator preview-confirm routes.
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
      section: ["packs", "github-projects", "checkouts", "constraints", "verification", "runbook"].indexOf(section) >= 0
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
      return payload && Array.isArray(payload.packs) ? payload.packs : [];
    });
  }

  function buildRegistrations() {
    return fetchJson(API_BASE + "/registrations").then(function (payload) {
      return payload && Array.isArray(payload.registrations) ? payload.registrations : [];
    });
  }

  function buildConfiguration() {
    return fetchJson(API_BASE + "/configuration");
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
      API_BASE + "/packs/" + encodeURIComponent(packName) + "/install/preview",
      {}
    );
  }

  function installPack(packName, previewDigest) {
    return postJson(
      API_BASE + "/packs/" + encodeURIComponent(packName) + "/install",
      { preview_digest: previewDigest, confirm: true }
    );
  }

  function buildWizardInventory() {
    return fetchJson(API_BASE + "/wizard/inventory").then(function (inventory) {
      var packs = inventory && Array.isArray(inventory.packs) ? inventory.packs : [];
      return Promise.all(packs.map(function (name) {
        return checkPack(name)
          .then(function (result) {
            return { name: name, status: result && result.ready ? "ready" : "blocked" };
          })
          .catch(function () { return { name: name, status: "not checked" }; });
      })).then(function (packOptions) {
        inventory.pack_options = packOptions;
        return inventory;
      });
    });
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
    workflow, detail, decisions, approvalReview, reviewDecision, onApproved, onReviewDecided
  ) {
    var summary = detail && detail.workflow ? detail.workflow : workflow;
    var policyRevision = summary.policy_revision;
    var planRevision = summary.plan_revision;
    var approval = summary.approval;
    var cards = detail && detail.kanban && Array.isArray(detail.kanban.cards)
      ? detail.kanban.cards
      : [];
    var decisionsList = decisions && decisions.decisions
      ? decisions.decisions
      : [];
    var recommendations = detail && Array.isArray(detail.recommendations)
      ? detail.recommendations
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
        )
      ),
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
        createElement(
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
      decisions === undefined
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
      reviewDecision === undefined
        ? createElement("p", { className: "daidala-workflow-loading" }, "Loading review evidence")
        : createElement(WorkflowReviewDisposition, {
            packet: reviewDecision,
            onDecided: onReviewDecided
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

  function ConfigurationPanel(props) {
    var tabState = useState(props.section || "packs");
    var tab = tabState[0];
    var setTab = tabState[1];

    useEffect(function () {
      if (props.section) setTab(props.section);
    }, [props.section]);

    return createElement(
      "section",
      { className: "daidala-config-section", "data-testid": "daidala-config" },
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
          createElement("div", null, createElement("dt", null, "Intake alias"), createElement("dd", null, registration.intake_credential)),
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
    var packsState = useState(undefined);
    var packs = packsState[0];
    var setPacks = packsState[1];
    var errorState = useState("");
    var error = errorState[0];
    var setError = errorState[1];

    function refreshPacks() {
      setError("");
      buildPacks()
        .then(setPacks)
        .catch(function (caught) {
          setError(caught.message);
          setPacks([]);
        });
    }

    useEffect(function () {
      refreshPacks();
    }, []);

    return createElement(
      "section",
      { className: "daidala-config", "data-testid": "daidala-pack-browser" },
      createElement(
        "header",
        { className: "daidala-config-header" },
        createElement("div", null,
          createElement("p", { className: "daidala-eyebrow" }, "Configuration"),
          createElement("h2", null, "Packs"),
          createElement("p", { className: "daidala-workflow-meta" },
            "Validate lifecycle declarations, inspect exact installed skill content, and repair readiness."
          )
        ),
        createElement("button", { type: "button", onClick: refreshPacks }, "Refresh packs")
      ),
      packs === undefined
        ? createElement("p", { className: "daidala-state daidala-state-loading" }, "Loading packs")
        : error
          ? createElement("p", { className: "daidala-banner daidala-banner-error" }, error)
          : createElement(
              "div",
              { className: "daidala-pack-grid" },
              packs.map(function (pack) {
                return createElement(PackCard, { key: pack.name, pack: pack });
              })
            )
    );
  }

  function PackCard(props) {
    var pack = props.pack;
    var checkState = useState(null);
    var check = checkState[0];
    var setCheck = checkState[1];
    var previewState = useState(null);
    var preview = previewState[0];
    var setPreview = previewState[1];
    var documentState = useState(null);
    var documentView = documentState[0];
    var setDocumentView = documentState[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var busyState = useState(false);
    var busy = busyState[0];
    var setBusy = busyState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];
    var projection = check || pack;
    var stages = Array.isArray(projection.stages) ? projection.stages : [];
    var hasExternal = pack.stages.some(function (stage) {
      return stage.skills.some(function (skill) { return skill.external; });
    });
    var status = !check
      ? "Not checked"
      : check.ready
        ? "Ready"
        : check.installable && check.actions.length > 0
          ? "Installation available"
          : "Blocked";

    function run(action, successMessage) {
      setBusy(true);
      setMessage("");
      return Promise.resolve(action())
        .then(function (value) {
          setMessage(successMessage);
          return value;
        })
        .catch(function (caught) {
          setMessage(caught.message);
          throw caught;
        })
        .finally(function () { setBusy(false); });
    }

    function runValidation() {
      run(function () { return validatePack(pack.name); }, "Pack declaration is valid.")
        .catch(function () {});
    }

    function runCheck() {
      run(function () { return checkPack(pack.name); }, "Readiness check complete.")
        .then(function (value) { setCheck(value); setPreview(null); setConfirmed(false); })
        .catch(function () {});
    }

    function runPreview() {
      run(function () { return previewPackInstall(pack.name); }, "Installation preview ready.")
        .then(function (value) { setCheck(value); setPreview(value); setConfirmed(false); })
        .catch(function () {});
    }

    function runInstall() {
      run(
        function () { return installPack(pack.name, preview.preview_digest); },
        "External skills installed and verified."
      )
        .then(function (value) {
          setCheck(value.pack);
          setPreview(null);
          setConfirmed(false);
        })
        .catch(function () {});
    }

    function loadContent(skillName) {
      run(
        function () { return buildPackSkillContent(pack.name, skillName); },
        "Loaded exact declared skill content."
      )
        .then(setDocumentView)
        .catch(function () {});
    }

    return createElement(
      "article",
      { className: "daidala-pack", "data-testid": "daidala-pack", "data-pack": pack.name },
      createElement(
        "header",
        { className: "daidala-pack-header" },
        createElement("div", null,
          createElement("h3", null, pack.name),
          createElement("p", { className: "daidala-workflow-meta" },
            pack.source + " @ " + pack.source_revision
          )
        ),
        createElement("span", {
          className: "daidala-pack-status is-" + status.toLowerCase().replace(/ /g, "-")
        }, status)
      ),
      createElement("p", { className: "daidala-pack-meta" },
        "Lifecycle: " + pack.lifecycle.join(" → ") + " · human gate after " + pack.human_gate_after
      ),
      createElement(
        "div",
        { className: "daidala-pack-actions" },
        createElement("button", { type: "button", disabled: busy, onClick: runValidation }, "Validate"),
        createElement("button", { type: "button", disabled: busy, onClick: runCheck }, "Check readiness"),
        hasExternal
          ? createElement("button", { type: "button", disabled: busy, onClick: runPreview }, "Preview installation")
          : createElement("span", { className: "daidala-workflow-meta" }, "Bundled adapter · check only")
      ),
      createElement(
        "div",
        { className: "daidala-pack-stages" },
        stages.map(function (stage) {
          return createElement(
            "section",
            { key: stage.id, className: "daidala-pack-stage" },
            createElement("h4", null, stage.id),
            createElement(
              "ul",
              null,
              stage.skills.map(function (skill) {
                var readiness = !check ? "not checked" : skill.ready ? "ready" : "not ready";
                return createElement(
                  "li",
                  { key: skill.name },
                  createElement("button", {
                    type: "button",
                    className: "daidala-skill",
                    onClick: function () { loadContent(skill.name); }
                  },
                    createElement("span", { className: "daidala-skill-name" }, skill.name),
                    createElement("span", { className: "daidala-skill-meta" },
                      skill.activation + " · " + (skill.external ? "external" : "bundled") + " · " + readiness
                    ),
                    createElement("span", { className: "daidala-skill-digest" },
                      "expected " + skill.expected_digest +
                      (skill.observed_digest ? " · observed " + skill.observed_digest : " · observed unavailable")
                    )
                  )
                );
              })
            )
          );
        })
      ),
      documentView
        ? createElement(
            "section",
            { className: "daidala-skill-document", "data-testid": "daidala-skill-content" },
            createElement("h4", null, documentView.skill + " · installed SKILL.md"),
            createElement("p", { className: "daidala-workflow-meta" },
              documentView.available
                ? String(documentView.byte_size) + " UTF-8 bytes"
                : documentView.unavailable_reason
            ),
            documentView.available
              ? createElement("pre", null, documentView.content)
              : createElement("p", null,
                  "Pinned target: " + (documentView.install_target || "bundled") +
                  " · expected digest " + documentView.expected_digest
                )
          )
        : null,
      preview
        ? createElement(
            "section",
            { className: "daidala-pack-preview", "data-testid": "daidala-pack-preview" },
            createElement("h4", null, "External skill installation preview"),
            createElement("p", { className: "daidala-skill-digest" },
              "Preview digest " + preview.preview_digest
            ),
            preview.actions.length
              ? createElement("ul", null, preview.actions.map(function (action) {
                  return createElement("li", { key: action.name },
                    action.name + " ← " + action.install_target
                  );
                }))
              : createElement("p", null, "No external installation actions are required."),
            preview.blockers.length
              ? createElement("p", { className: "daidala-banner daidala-banner-error" },
                  preview.blockers.join("; ")
                )
              : null,
            preview.actions.length && preview.installable
              ? createElement("label", { className: "daidala-pack-confirm" },
                  createElement("input", {
                    type: "checkbox",
                    checked: confirmed,
                    onChange: function (event) { setConfirmed(event.target.checked); }
                  }),
                  "I confirm these exact external skill installations"
                )
              : null,
            preview.actions.length && preview.installable
              ? createElement("button", {
                  type: "button",
                  disabled: busy || !confirmed,
                  onClick: runInstall
                }, "Install external skills")
              : null
          )
        : null,
      message ? createElement("p", { role: "status" }, message) : null
    );
  }

  var WIZARD_STAGES = ["define", "plan", "implement", "verify", "review", "deliver"];

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
      project_id: "", pack: "", board_slug: "", goal: "", worker_default: "",
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
          return Object.assign({}, current, {
            project_id: projects.some(function (row) {
              return row.project_id === (saved.project_id || current.project_id);
            }) ? (saved.project_id || current.project_id) : "",
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
        board_slug: form.board_slug,
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
      return { selection: { project_id: form.project_id }, request: request };
    }

    function runReadiness() {
      setBusy(true); setError("");
      wizardReadiness(envelope()).then(function (result) {
        setReadiness(result.readiness); setPreview(null); setConfirmed(false);
      }).catch(function (reason) {
        setReadiness(null); setError("Readiness did not pass: " + errorText(reason));
      }).finally(function () { setBusy(false); });
    }

    function runPreview() {
      setBusy(true); setError("");
      wizardPreview(envelope()).then(function (result) {
        setReadiness(result.readiness); setPreview(result); setConfirmed(false);
      }).catch(function (reason) {
        setPreview(null); setError("Preview could not be created: " + errorText(reason));
      }).finally(function () { setBusy(false); });
    }

    function runStart() {
      if (!preview || !confirmed) return;
      setBusy(true); setError("");
      wizardStart(Object.assign({}, envelope(), {
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
            project_id: form.project_id, pack: form.pack, board_slug: form.board_slug,
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
    var boards = inventory && Array.isArray(inventory.boards) ? inventory.boards : [];
    var packs = inventory && Array.isArray(inventory.pack_options) ? inventory.pack_options : [];
    var policySources = inventory && Array.isArray(inventory.policy_sources) ? inventory.policy_sources : [];
    var hasRequest = form.project_id && form.pack && form.board_slug && form.goal.trim() &&
      WIZARD_STAGES.every(function (stage) { return form.stage_profiles[stage]; });

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
          createElement("div", { className: "daidala-wizard-section-heading" },
            select("Registered repository", form.project_id, function (value) { change("project_id", value); }, projects.map(function (row) { return { value: row.project_id, label: row.project_id + " · " + row.repository }; })),
            createElement("a", { href: "/daidala?section=runbook&return=start-workflow", onClick: function (event) { navigateDashboard(event, "/daidala?section=runbook&return=start-workflow"); } }, "Register repository")
          ),
          createElement("label", { className: "daidala-wizard-field" }, createElement("span", null, "Requested outcome / Prompt"),
            createElement("textarea", { value: form.goal, rows: 3, onChange: function (event) { change("goal", event.target.value); } })
          ),
          createElement("div", { className: "daidala-board-control" },
            select("Board · existing", form.board_slug, function (value) { change("board_slug", value); }, boards.map(function (row) { return { value: row.slug, label: row.name ? row.name + " · " + row.slug : row.slug }; })),
            createElement("label", { className: "daidala-wizard-field" }, createElement("span", null, "New board slug"),
              createElement("input", { value: form.board_draft, onChange: function (event) { change("board_draft", event.target.value); } })
            ),
            createElement("label", { className: "daidala-wizard-field" }, createElement("span", null, "New board display name"),
              createElement("input", { value: form.board_name, onChange: function (event) { change("board_name", event.target.value); } })
            ),
            createElement("button", { type: "button", disabled: busy || !form.board_draft || !form.board_name.trim(), onClick: previewBoard }, "Create board")
          ),
          boardPreview ? createElement("div", { className: "daidala-confirm-box" },
            createElement("p", null, "Board preview is ready for " + boardPreview.preview.slug + "."),
            createElement("label", null, createElement("input", { type: "checkbox", checked: boardConfirmed, onChange: function (event) { setBoardConfirmed(event.target.checked); } }), " I confirm creating this exact board"),
            createElement("button", { type: "button", disabled: busy || !boardConfirmed, onClick: createBoard }, "Create board now")
          ) : null,
          select("Worker profile default", form.worker_default, changeWorker, profiles.map(function (name) { return { value: name, label: name }; })),
          createElement("details", { className: "daidala-wizard-advanced" },
            createElement("summary", null, "Advanced workflow settings"),
            WIZARD_STAGES.map(function (stage) {
              return select(stage.charAt(0).toUpperCase() + stage.slice(1), form.stage_profiles[stage] || "", function (value) { changeStage(stage, value); }, profiles.map(function (name) { return { value: name, label: name }; }));
            }),
            createElement("label", { className: "daidala-wizard-field" }, createElement("span", null, "Workflow identity (optional)"),
              createElement("input", { value: form.workflow_id, onChange: function (event) { change("workflow_id", event.target.value); } })
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
          readiness ? createElement("ul", null, readiness.checks.map(function (check) {
            return createElement("li", { key: check.id, className: check.passed ? "is-ready" : "is-blocked" }, (check.passed ? "✓ " : "× ") + check.id);
          })) : createElement("p", null, "Run a non-mutating check after completing the form."),
          createElement("button", { type: "button", disabled: !hasRequest || busy, onClick: runReadiness }, "Check readiness")
        )
      ) : null,
      preview ? createElement("section", { className: "daidala-wizard-preview" },
        createElement("h3", null, "Preview result · non-mutating"),
        createElement("p", null, "Digest " + preview.preview_digest),
        createElement("label", null, createElement("input", { type: "checkbox", checked: confirmed, onChange: function (event) { setConfirmed(event.target.checked); } }), " I confirm applying this exact preview"),
        createElement("button", { type: "button", disabled: busy || !confirmed, onClick: runStart }, "Start now")
      ) : null,
      inventory ? createElement("div", { className: "daidala-wizard-actions" }, createElement("button", { type: "button", disabled: !hasRequest || busy, onClick: runPreview }, "Preview workflow")) : null,
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
    var initialRoute = dashboardRoute();
    var _a = useState(false), starting = _a[0], setStarting = _a[1];
    var _b = useState(initialRoute.workflowId), openWorkflowId = _b[0], setOpenWorkflowId = _b[1];
    var _c = useState(""), startNotice = _c[0], setStartNotice = _c[1];
    var _d = useState(initialRoute), route = _d[0], setRoute = _d[1];
    var returnedSourceState = useState(null), returnedSource = returnedSourceState[0], setReturnedSource = returnedSourceState[1];

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
    var listedWorkflows = openWorkflowId
      ? workflows.filter(function (row) { return row.workflow_id !== openWorkflowId; })
      : workflows;
    var firstLoad = workflowsState.loading && workflows.length === 0;
    var hostDown = workflowsState.snapshot === null;
    var healthDown = health.snapshot && health.snapshot.success === false;

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
        healthDown
          ? createElement(
              "p",
              { className: "daidala-banner daidala-banner-error" },
              "Daidala backend is unreachable."
            )
          : null
      ),
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
              planRevision: route.workflowId === openWorkflowId ? route.planRevision : null
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
          : workflows.length === 0
            ? createElement(
                "p",
                {
                  className: "daidala-state daidala-state-empty",
                  "data-testid": "daidala-no-workflows"
                },
                "No Daidala workflows"
              )
            : createElement(
                "section",
                { className: "daidala-workflows", "data-testid": "daidala-workflows" },
                listedWorkflows.map(function (row) {
                  return createElement(WorkflowDetail, {
                    key: row.workflow_id,
                    workflow: row
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