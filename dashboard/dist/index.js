/*
 * Daidala dashboard UI — bounded operator surface.
 *
 * The plugin renders two components through the Hermes dashboard plugin SDK:
 *
 *   - the /daidala tab (Page) lists workflows, links live Kanban snapshots
 *     to Daidala policy identity, and surfaces pending decisions;
 *   - the sessions:top slot (Slot) renders a compact pending-decision count.
 *
 * Live state is polled on a fixed >= 5 second cadence while the page is visible;
 * the timer is paused when the tab is hidden. Pack installation, workflow setup,
 * and constraint replacement use closed preview-confirm routes only.
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
          .then(function (result) { return result && result.ready ? name : null; })
          .catch(function () { return null; });
      })).then(function (readyPacks) {
        inventory.ready_packs = readyPacks.filter(Boolean);
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
          var readyPacks = Array.isArray(next.ready_packs) ? next.ready_packs : [];
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
            pack: readyPacks.indexOf(saved.pack || current.pack) >= 0
              ? (saved.pack || current.pack) : readyPacks[0] || "",
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
    var packs = inventory && Array.isArray(inventory.ready_packs) ? inventory.ready_packs : [];
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
            select("Pack · installed and ready", form.pack, function (value) { change("pack", value); }, packs.map(function (name) { return { value: name, label: name }; })),
            createElement("a", { href: "/daidala?section=packs&return=start-workflow", onClick: function (event) { navigateDashboard(event, "/daidala?section=packs&return=start-workflow"); } }, "Manage packs")
          ),
          select("Registered repository", form.project_id, function (value) { change("project_id", value); }, projects.map(function (row) { return { value: row.project_id, label: row.project_id + " · " + row.repository }; })),
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

  function Page() {
    var health = useVisiblePolling(POLL_MS, buildHealth);
    var workflowsState = useVisiblePolling(POLL_MS, buildWorkflows);
    var _a = useState(false), starting = _a[0], setStarting = _a[1];
    var _b = useState(null), openWorkflowId = _b[0], setOpenWorkflowId = _b[1];
    var _c = useState(""), startNotice = _c[0], setStartNotice = _c[1];

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
        createElement("button", {
          type: "button",
          className: "daidala-refresh",
          onClick: function () { setStarting(true); }
        }, "Start workflow"),
        healthDown
          ? createElement(
              "p",
              { className: "daidala-banner daidala-banner-error" },
              "Daidala backend is unreachable."
            )
          : null
      ),
      starting
        ? createElement(StartWorkflow, {
            onClose: function () { setStarting(false); },
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
        : createElement(React.Fragment, null,
      openWorkflowId
        ? createElement("section", { className: "daidala-workflows", "data-testid": "daidala-opened-workflow" },
            startNotice ? createElement("p", { role: "status", className: "daidala-banner" }, startNotice) : null,
            createElement(WorkflowDetail, { workflow: { workflow_id: openWorkflowId } })
          )
        : null,
      createElement(PackBrowser),
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