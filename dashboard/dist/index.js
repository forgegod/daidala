/*
 * Wingstaff dashboard UI — Phase 3 read-only surface.
 *
 * The plugin renders two components through the Hermes dashboard plugin SDK:
 *
 *   - the /wingstaff tab (Page) lists workflows, links live Kanban snapshots
 *     to Wingstaff policy identity, and surfaces pending decisions;
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
  var API_BASE = "/api/plugins/wingstaff";
  var PLUGIN_NAME = "wingstaff";

  function fetchJson(url) {
    return fetch(url, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        Authorization: "Bearer " + window.__HERMES_SESSION_TOKEN__
      }
    }).then(function (response) {
      if (!response.ok) {
        var error = new Error("request failed: " + response.status);
        error.status = response.status;
        throw error;
      }
      return response.json();
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
    var cardClass = "ws-card ws-card-" + card.stage + " is-" + card.status;
    var blockReason = card.block_reason ? card.block_reason : "";
    return createElement(
      "li",
      { key: card.task_id, className: cardClass, "data-testid": "ws-card" },
      createElement("span", { className: "ws-card-stage" }, card.stage),
      createElement("span", { className: "ws-card-status" }, card.status),
      createElement("span", { className: "ws-card-assignee" }, card.assignee || "—"),
      blockReason
        ? createElement("span", { className: "ws-card-reason" }, blockReason)
        : null
    );
  }

  function renderDecisionItem(action) {
    return createElement(
      "li",
      {
        key: action.action_kind + (action.card_id || ""),
        className: "ws-decision ws-decision-" + action.action_kind,
        "data-testid": "ws-decision"
      },
      createElement("span", { className: "ws-decision-kind" }, actionBadge(action)),
      createElement("span", { className: "ws-decision-rationale" }, summarizeAction(action)),
      action.card_id
        ? createElement(
            "span",
            { className: "ws-decision-card" },
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
        className: "ws-workflow",
        key: workflow.workflow_id,
        "data-testid": "ws-workflow",
        "data-workflow-id": workflow.workflow_id
      },
      createElement(
        "header",
        { className: "ws-workflow-header" },
        createElement("h3", { className: "ws-workflow-title" }, workflow.workflow_id),
        createElement(
          "p",
          { className: "ws-workflow-meta" },
          workflow.board_slug + " · " + workflow.pack_name + " · policy " + policyRevision
        )
      ),
      createElement(
        "p",
        { className: "ws-workflow-goal" },
        workflow.requested_goal || ""
      ),
      createElement(
        "dl",
        { className: "ws-workflow-identity" },
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
                { className: "ws-workflow-digest" },
                workflow.current_constraints_digest
              )
            )
          : null
      ),
      createElement(
        "h4",
        { className: "ws-workflow-section-title" },
        "Live Kanban"
      ),
      detail === undefined
        ? createElement(
            "p",
            { className: "ws-workflow-loading" },
            "Loading card status"
          )
        : detail === null || (detail.kanban && detail.kanban.available === false)
          ? createElement(
              "p",
              { className: "ws-workflow-unavailable" },
              "Live Kanban state unavailable"
            )
          : cards.length === 0
            ? createElement(
                "p",
                { className: "ws-workflow-empty" },
                "No cards yet"
              )
            : createElement(
                "ul",
                { className: "ws-workflow-cards", "data-testid": "ws-cards" },
                cards.map(renderCardRow)
              ),
      createElement(
        "h4",
        { className: "ws-workflow-section-title" },
        "Pending decisions"
      ),
      decisions === undefined
        ? createElement(
            "p",
            { className: "ws-workflow-loading" },
            "Loading decisions"
          )
        : !decisions.available
          ? createElement(
              "p",
              { className: "ws-workflow-unavailable" },
              "Live Kanban state unavailable"
            )
          : decisionsList.length === 0
            ? createElement(
                "p",
                { className: "ws-workflow-empty" },
                "No pending human decision"
              )
            : createElement(
                "ul",
                { className: "ws-workflow-decisions", "data-testid": "ws-decisions" },
                decisionsList.map(renderDecisionItem)
              )
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
      { className: "ws-root", "data-testid": "wingstaff-tab" },
      createElement(
        "header",
        { className: "ws-root-header" },
        createElement("h1", null, "Wingstaff"),
        createElement(
          "p",
          { className: "ws-root-subtitle" },
          "Read-only view over the active Wingstaff profile."
        ),
        createElement(
          "button",
          {
            type: "button",
            className: "ws-refresh",
            "data-testid": "ws-refresh",
            onClick: refreshAll
          },
          "Refresh"
        ),
        healthDown
          ? createElement(
              "p",
              { className: "ws-banner ws-banner-error" },
              "Wingstaff backend is unreachable."
            )
          : null
      ),
      firstLoad
        ? createElement(
            "p",
            { className: "ws-state ws-state-loading", "data-testid": "ws-loading" },
            "Loading workflows"
          )
        : hostDown
          ? createElement(
              "p",
              {
                className: "ws-state ws-state-unavailable",
                "data-testid": "ws-host-unavailable"
              },
              "Live Kanban state unavailable"
            )
          : workflows.length === 0
            ? createElement(
                "p",
                {
                  className: "ws-state ws-state-empty",
                  "data-testid": "ws-no-workflows"
                },
                "No Wingstaff workflows"
              )
            : createElement(
                "section",
                { className: "ws-workflows", "data-testid": "ws-workflows" },
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
        className: "ws-slot",
        "data-testid": "wingstaff-slot",
        title: "Wingstaff decisions: " + decisionCount
      },
      "Wingstaff decisions: " + (hostDown ? "?" : String(decisionCount))
    );
  }

  window.__HERMES_PLUGINS__.register(PLUGIN_NAME, Page);
  window.__HERMES_PLUGINS__.registerSlot(PLUGIN_NAME, "sessions:top", Slot);
})();