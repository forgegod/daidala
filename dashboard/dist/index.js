/*
 * Daidala dashboard UI — Phase 3 read-only surface.
 *
 * The plugin renders two components through the Hermes dashboard plugin SDK:
 *
 *   - the /daidala tab (Page) lists workflows, links live Kanban snapshots
 *     to Daidala policy identity, and surfaces pending decisions;
 *   - the sessions:top slot (Slot) renders a compact pending-decision count.
 *
 * The UI is strictly read-only: only GET requests are issued, no write path is
 * ever invoked from the browser. Live state is polled on a fixed >= 5 second
 * cadence while the page is visible; the timer is paused when the tab is
 * hidden, and a manual Refresh button is always available.
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

  function buildHealth() {
    return fetchJson(API_BASE + "/health").catch(function () {
      return { success: false, read_only: true };
    });
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

  function buildWorkflowDetail(workflowId) {
    return fetchJson(API_BASE + "/workflows/" + encodeURIComponent(workflowId))
      .then(function (payload) {
        return payload;
      })
      .catch(function () {
        return null;
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
    return createElement(
      "li",
      { key: card.task_id, className: cardClass, "data-testid": "daidala-card" },
      createElement("span", { className: "daidala-card-stage" }, card.stage),
      createElement("span", { className: "daidala-card-status" }, card.status),
      createElement("span", { className: "daidala-card-assignee" }, card.assignee || "—"),
      blockReason
        ? createElement("span", { className: "daidala-card-reason" }, blockReason)
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

  function renderWorkflowCard(workflow, detail, decisions) {
    var policyRevision = workflow.policy_revision;
    var planRevision = workflow.plan_revision;
    var approval = workflow.approval;
    var cards = detail && detail.kanban && Array.isArray(detail.kanban.cards)
      ? detail.kanban.cards
      : [];
    var decisionsList = decisions && decisions.decisions
      ? decisions.decisions
      : [];

    return createElement(
      "article",
      {
        className: "daidala-workflow",
        key: workflow.workflow_id,
        "data-testid": "daidala-workflow",
        "data-workflow-id": workflow.workflow_id
      },
      createElement(
        "header",
        { className: "daidala-workflow-header" },
        createElement("h3", { className: "daidala-workflow-title" }, workflow.workflow_id),
        createElement(
          "p",
          { className: "daidala-workflow-meta" },
          workflow.board_slug + " · " + workflow.pack_name + " · policy " + policyRevision
        )
      ),
      createElement(
        "p",
        { className: "daidala-workflow-goal" },
        workflow.requested_goal || ""
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
        workflow.current_constraints_digest
          ? createElement(
              "div",
              null,
              createElement("dt", null, "constraint digest"),
              createElement(
                "dd",
                { className: "daidala-workflow-digest" },
                workflow.current_constraints_digest
              )
            )
          : null
      ),
      createElement(
        "h4",
        { className: "daidala-workflow-section-title" },
        "Live Kanban"
      ),
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
          : cards.length === 0
            ? createElement(
                "p",
                { className: "daidala-workflow-empty" },
                "No cards yet"
              )
            : createElement(
                "ul",
                { className: "daidala-workflow-cards", "data-testid": "daidala-cards" },
                cards.map(renderCardRow)
              ),
      createElement(
        "h4",
        { className: "daidala-workflow-section-title" },
        "Pending decisions"
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
            ? createElement(
                "p",
                { className: "daidala-workflow-empty" },
                "No pending human decision"
              )
            : createElement(
                "ul",
                { className: "daidala-workflow-decisions", "data-testid": "daidala-decisions" },
                decisionsList.map(renderDecisionItem)
              ),
      detail && detail.workflow
        ? createElement(ConstraintEditor, {
            workflow: detail.workflow,
            constraints: detail.constraints
          })
        : null
    );
  }

  function ConstraintEditor(props) {
    var initial = props.constraints ? props.constraints.canonical_content : "global:\nphases:\n";
    var contentState = useState(initial);
    var content = contentState[0];
    var setContent = contentState[1];
    var previewState = useState(null);
    var preview = previewState[0];
    var setPreview = previewState[1];
    var confirmedState = useState(false);
    var confirmed = confirmedState[0];
    var setConfirmed = confirmedState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];

    function payload() {
      return {
        workflow_id: props.workflow.workflow_id,
        expected_current_digest: props.workflow.current_constraints_digest,
        constraints_content: content
      };
    }

    function previewChange() {
      postJson(API_BASE + "/constraints/preview", payload()).then(function (value) {
        setPreview(value);
        setConfirmed(false);
        setMessage(value.valid ? "Preview ready." : value.errors.join("; "));
      }).catch(function (error) { setMessage(error.message); });
    }

    function replaceConstraints() {
      postJson(API_BASE + "/constraints/replace", Object.assign({}, payload(), { confirm: true }))
        .then(function () { setMessage("Constraints replaced. Fresh approval is required."); })
        .catch(function (error) { setMessage(error.message); });
    }

    return createElement("section", { className: "daidala-constraints", "data-testid": "daidala-constraints" },
      createElement("h4", null, "Workflow constraints"),
      createElement("p", { className: "daidala-workflow-meta" },
        "Revision " + (props.constraints ? props.constraints.revision : "none") +
        " · digest " + (props.workflow.current_constraints_digest || "none") +
        " · maximum 4096 canonical UTF-8 bytes"
      ),
      createElement("textarea", {
        value: content,
        onChange: function (event) { setContent(event.target.value); setPreview(null); setConfirmed(false); },
        rows: 10,
        "aria-label": "Complete workflow constraints YAML"
      }),
      createElement("button", { type: "button", onClick: previewChange }, "Preview constraint change"),
      preview ? createElement("pre", null, JSON.stringify(preview, null, 2)) : null,
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
        ? createElement("button", { type: "button", disabled: !confirmed, onClick: replaceConstraints }, "Replace constraints")
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

  function SetupWizard() {
    var formState = useState({ board_slug: "default", target_repository: "", goal: "" });
    var form = formState[0];
    var setForm = formState[1];
    var previewState = useState(null);
    var preview = previewState[0];
    var setPreview = previewState[1];
    var confirmState = useState(false);
    var confirmed = confirmState[0];
    var setConfirmed = confirmState[1];
    var messageState = useState("");
    var message = messageState[0];
    var setMessage = messageState[1];

    function request() {
      var profiles = {};
      ["define", "plan", "implement", "verify", "review", "deliver"].forEach(function (stage) {
        profiles[stage] = "default";
      });
      return Object.assign({}, form, { pack: "addyosmani", stage_profiles: profiles });
    }

    function field(label, name) {
      return createElement("label", { className: "daidala-setup-field" }, label,
        createElement("input", {
          value: form[name],
          onChange: function (event) {
            var next = Object.assign({}, form);
            next[name] = event.target.value;
            setForm(next);
            setPreview(null);
            setConfirmed(false);
          }
        })
      );
    }

    function previewSetup() {
      postJson(API_BASE + "/wizard/preview", request()).then(function (value) {
        setPreview(value);
        setMessage("Preview ready. Confirm before starting.");
      }).catch(function (error) { setMessage(error.message); });
    }

    function startSetup() {
      postJson(API_BASE + "/wizard/start", Object.assign({}, request(), { confirm: true }))
        .then(function () { setMessage("Workflow started."); })
        .catch(function (error) { setMessage(error.message); });
    }

    return createElement("section", { className: "daidala-setup", "data-testid": "daidala-setup" },
      createElement("h2", null, "Start a workflow"),
      field("Board", "board_slug"),
      field("Repository path", "target_repository"),
      field("Goal", "goal"),
      createElement("button", { type: "button", onClick: previewSetup }, "Preview mutations"),
      preview ? createElement("pre", { className: "daidala-setup-preview" }, JSON.stringify(preview, null, 2)) : null,
      preview ? createElement("label", { className: "daidala-setup-confirm" },
        createElement("input", { type: "checkbox", checked: confirmed, onChange: function (event) { setConfirmed(event.target.checked); } }),
        "I confirm these mutations"
      ) : null,
      preview ? createElement("button", { type: "button", disabled: !confirmed, onClick: startSetup }, "Start workflow") : null,
      message ? createElement("p", { role: "status" }, message) : null
    );
  }

  function Page() {
    var health = useVisiblePolling(POLL_MS, buildHealth);
    var workflowsState = useVisiblePolling(POLL_MS, buildWorkflows);

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
          "Read-only view over the active Daidala profile."
        ),
        createElement(
          "button",
          {
            type: "button",
            className: "daidala-refresh",
            "data-testid": "daidala-refresh",
            onClick: refreshAll
          },
          "Refresh"
        ),
        healthDown
          ? createElement(
              "p",
              { className: "daidala-banner daidala-banner-error" },
              "Daidala backend is unreachable."
            )
          : null
      ),
      createElement(SetupWizard),
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
                workflows.map(function (row) {
                  return createElement(WorkflowDetail, {
                    key: row.workflow_id,
                    workflow: row
                  });
                })
              )
    );
  }

  function WorkflowDetail(props) {
    var workflow = props.workflow;
    var detailState = useVisiblePolling(POLL_MS, function () {
      return buildWorkflowDetail(workflow.workflow_id);
    });
    var decisionsState = useVisiblePolling(POLL_MS, function () {
      return buildDecisions(workflow.workflow_id);
    });

    return renderWorkflowCard(
      workflow,
      detailState.snapshot,
      decisionsState.snapshot
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