#!/usr/bin/env node

import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const SCREENS = [
  {
    capability: "CAP-0003",
    slug: "CAP-0003-operator-dashboard",
    title: "Operator dashboard",
    html: "html/CAP-0003-operator-dashboard.html",
    png: "exports/CAP-0003-operator-dashboard.png",
    viewport: { width: 1440, height: 960 },
  },
  {
    capability: "CAP-0004",
    slug: "CAP-0004-github-repository-registration",
    title: "GitHub repository registration",
    html: "html/CAP-0004-github-repository-registration.html",
    png: "exports/CAP-0004-github-repository-registration.png",
    viewport: { width: 1440, height: 960 },
  },
  {
    capability: "CAP-0005",
    slug: "CAP-0005-reviewed-github-branch-delivery",
    title: "Reviewed GitHub branch delivery",
    html: "html/CAP-0005-reviewed-github-branch-delivery.html",
    png: "exports/CAP-0005-reviewed-github-branch-delivery.png",
    viewport: { width: 1440, height: 960 },
  },
  {
    capability: "CAP-0006",
    slug: "CAP-0006-repository-policy-bootstrap",
    title: "Repository policy bootstrap",
    html: "html/CAP-0006-repository-policy-bootstrap.html",
    png: "exports/CAP-0006-repository-policy-bootstrap.png",
    viewport: { width: 1440, height: 960 },
  },
  {
    capability: "CAP-0007",
    slug: "CAP-0007-complete-workflow-pack-installation",
    title: "Complete workflow-pack installation",
    html: "html/CAP-0007-complete-workflow-pack-installation.html",
    png: "exports/CAP-0007-complete-workflow-pack-installation.png",
    viewport: { width: 1440, height: 960 },
  },
];

function buildOperatorDashboardHtml(screen) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${screen.capability} — ${screen.title}</title>
  <style>
    :root { color-scheme:dark; --bg:#001f1d; --panel:#032725; --soft:#082f2c; --line:#244845; --text:#f4ead8; --muted:#8fa6a1; --cream:#ffe6ca; --ink:#102321; --amber:#ffc933; --green:#42ea92; --red:#ff786f; --blue:#5688ff; }
    * { box-sizing:border-box; } body { margin:0; width:1440px; height:960px; overflow:hidden; background:var(--bg); color:var(--text); font:14px/1.4 Inter,ui-sans-serif,system-ui,sans-serif; }
    button,input,select { font:inherit; } .shell { display:grid; grid-template-columns:240px 1fr; height:960px; } aside { padding:18px 15px; border-right:1px solid var(--line); display:flex; flex-direction:column; } .brand { font-size:19px; font-weight:800; line-height:1; letter-spacing:.08em; }
    nav { display:grid; gap:3px; margin-top:25px; } nav div { padding:7px 11px; color:#b8c4c0; font-size:11px; letter-spacing:.13em; text-transform:uppercase; } nav .active { background:#29413f; color:var(--cream); font-weight:800; } .system { margin-top:auto; padding:12px; border:1px solid var(--line); color:var(--muted); font-size:11px; }
    main { min-width:0; } header { height:72px; padding:18px 28px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); } h1,h2,h3,h4,p { margin-top:0; } h1 { margin:0; font-size:18px; letter-spacing:.09em; } .views { display:flex; } .view { padding:10px 20px; border:1px solid var(--line); color:var(--muted); text-transform:uppercase; font-size:11px; letter-spacing:.1em; } .view.active { color:var(--ink); background:var(--cream); border-color:var(--cream); font-weight:800; }
    .workspace { padding:20px 28px; } .eyebrow { margin-bottom:5px; color:var(--blue); font-size:10px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; } .intro { color:var(--muted); } .config-tabs { display:flex; gap:6px; margin:13px 0; } .config-tabs span { padding:8px 12px; border:1px solid var(--line); border-radius:6px; } .config-tabs .active { color:var(--blue); border-color:var(--blue); }
    .pack-head { display:grid; grid-template-columns:1fr 265px; align-items:end; gap:18px; padding:18px; border:1px solid var(--line); background:var(--panel); } label { display:block; color:var(--muted); font-size:10px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; } select,input { width:100%; margin-top:7px; padding:11px 12px; border:1px solid var(--line); border-radius:6px; background:#001a18; color:var(--cream); }
    .layout { display:grid; grid-template-columns:410px 1fr; gap:14px; margin-top:14px; } .card { padding:18px; border:1px solid var(--line); border-radius:8px; background:var(--panel); } .pack-title { display:flex; align-items:start; justify-content:space-between; gap:12px; } .pack-title h3 { margin-bottom:4px; font-size:23px; } .source { color:var(--muted); font-size:12px; overflow-wrap:anywhere; } .badge { display:inline-block; padding:5px 8px; border:1px solid currentColor; border-radius:999px; font-size:10px; font-weight:800; text-transform:uppercase; } .blocked { color:var(--red); }
    .actions { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:16px 0; } button { padding:11px; border:1px solid var(--line); border-radius:6px; background:transparent; color:var(--text); font-weight:700; } button.primary { border-color:var(--green); color:var(--green); } .facts { display:grid; grid-template-columns:1fr 1fr; gap:8px; } .fact,.stage { padding:11px; border:1px solid var(--line); border-radius:6px; } .fact span,.stage span { display:block; color:var(--muted); font-size:9px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; } .fact b { display:block; margin-top:5px; font-size:16px; }
    .lifecycle { margin-top:16px; } .lifecycle p { margin-bottom:9px; color:var(--muted); font-size:12px; } .stages { display:grid; grid-template-columns:repeat(3,1fr); gap:7px; } .stage { display:flex; align-items:center; justify-content:space-between; } .stage b { color:var(--green); }
    .notice { margin-bottom:12px; padding:10px 12px; border:1px solid #675700; border-radius:6px; color:var(--amber); background:#2c2500; } .inventory-head { display:flex; justify-content:space-between; } .inventory-head p { color:var(--muted); } .filters { display:grid; grid-template-columns:1fr 150px; gap:8px; margin-bottom:12px; } .filters button { margin-top:7px; }
    table { width:100%; border-collapse:collapse; table-layout:fixed; } th,td { padding:10px 8px; border-top:1px solid var(--line); text-align:left; vertical-align:top; } th { color:var(--muted); font-size:9px; letter-spacing:.08em; text-transform:uppercase; } td:first-child { color:var(--cream); font-weight:700; } td small { display:block; margin-top:4px; color:var(--muted); font-weight:400; } .warning { color:var(--amber); } .missing { color:var(--red); } .detail { color:var(--cream); text-align:right; }
    .footnote { margin-top:10px; color:var(--muted); font-size:11px; } .annotation { position:fixed; right:14px; bottom:10px; color:#617b77; font-size:10px; }
  </style>
</head>
<body><div class="shell"><aside><div class="brand">HERMES<br>AGENT</div><nav><div>Chat</div><div>Sessions</div><div>Files</div><div>Models</div><div>Logs</div><div>Cron</div><div>Skills</div><div>Plugins</div><div>MCP</div><div>Channels</div><div>Profiles</div><div class="active">Daidala</div></nav><div class="system">Gateway status: Running<br>Active sessions: 0</div></aside>
<main><header><h1>Daidala</h1><div class="views"><div class="view">Workflows</div><div class="view">Artifacts</div><div class="view active">Config</div></div></header>
<section class="workspace"><p class="eyebrow">Configuration</p><p class="intro">Profile-local settings use server-derived identity and explicit preview confirmation.</p><div class="config-tabs"><span class="active">Packs</span><span>GitHub Repositories</span><span>GitHub Projects</span><span>Checkouts</span><span>Constraints</span><span>Verification</span><span>Runbook</span></div>
<section class="pack-head"><div><p class="eyebrow">Configuration</p><h2>Workflow packs</h2><p class="intro">Install a complete immutable catalog once; activate only the skills each lifecycle stage needs.</p></div><label>Pack<select><option>addyosmani</option><option>aidlc</option></select></label></section>
<div class="layout"><article class="card"><div class="pack-title"><div><p class="eyebrow">Selected workflow pack</p><h3>addyosmani</h3><div class="source">forgegod/addyosmani-agent-skills @ bf223959faae</div></div><span class="badge blocked">Blocked</span></div><div class="actions"><button class="primary">Retry 23 missing skills</button><button>Refresh readiness</button></div><div class="facts"><div class="fact"><span>Catalog</span><b>24 skills</b></div><div class="fact"><span>Installed</span><b>1 / 24</b></div><div class="fact"><span>Active profile</span><b>demo-controller</b></div><div class="fact"><span>Digest warnings</span><b>1</b></div></div><div class="lifecycle"><h4>Lifecycle</h4><p>Stage bindings select activation; the catalog owns installation. 4 catalog-only.</p><div class="stages"><div class="stage"><span>Define</span><b>3</b></div><div class="stage"><span>Plan</span><b>1</b></div><div class="stage"><span>Implement</span><b>4</b></div><div class="stage"><span>Verify</span><b>3</b></div><div class="stage"><span>Review</span><b>4</b></div><div class="stage"><span>Deliver</span><b>6</b></div></div></div><p class="footnote">Install preview names the shared Hermes skill store. Enable and disable confirmations affect only the active profile.</p></article>
<article class="card"><div class="notice">Digest mismatch warning. The installed skill remains available.</div><div class="inventory-head"><div><h3>Skill inventory</h3><p>20 stage-mapped · 4 catalog-only</p></div><strong>4 of 24 shown</strong></div><div class="filters"><label>Search skills<input placeholder="Search skills or lifecycle stage"></label><button>Catalog-only 4</button></div><table><thead><tr><th style="width:31%">Skill</th><th style="width:22%">Status</th><th style="width:25%">Lifecycle role</th><th>Activation</th><th></th></tr></thead><tbody><tr><td>api-and-interface-design<small>Catalog only</small></td><td class="missing">Not installed</td><td>Available outside lifecycle</td><td>Manual</td><td class="detail">Details</td></tr><tr><td>browser-testing-with-devtools</td><td class="missing">Not installed</td><td>verify</td><td>conditional</td><td class="detail">Details</td></tr><tr><td>code-review-and-quality</td><td class="missing">Not installed</td><td>review</td><td>required</td><td class="detail">Details</td></tr><tr><td>test-driven-development</td><td class="warning">Ready with warning</td><td>implement, verify</td><td>conditional</td><td class="detail">Details</td></tr></tbody></table><button style="width:100%;margin-top:12px">Show all 24 skills</button></article></div></section></main></div><div class="annotation">Static capability wireframe · synthetic data · no runtime authority</div></body></html>`;
}

function buildCompletePackInstallationProgressHtml(screen) {
  const progressStyles = `
    .install-progress { display:flex; align-items:baseline; gap:10px; margin:0 0 16px; padding:12px; border:1px solid var(--green); border-radius:6px; background:#06372f; }
    .install-progress strong { flex:0 0 auto; color:var(--green); white-space:nowrap; }
    .install-progress span { min-width:0; color:var(--cream); overflow-wrap:anywhere; }`;
  const progress = `<div class="install-progress" role="status" aria-live="polite"><strong>Installing skill 8 / 23</strong><span>debugging-and-error-recovery</span></div>`;
  return buildOperatorDashboardHtml(screen)
    .replace("  </style>", `${progressStyles}\n  </style>`)
    .replace("Retry 23 missing skills", "Installing…")
    .replace("<div class=\"facts\">", `${progress}<div class="facts">`);
}

function buildRepositoryRegistrationHtml(screen) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${screen.capability} — ${screen.title}</title>
  <style>
    :root { color-scheme: dark; --bg:#001f1d; --panel:#032725; --soft:#082f2c; --line:#244845; --text:#f4ead8; --muted:#8fa6a1; --cream:#ffe6ca; --ink:#102321; --amber:#ffc933; --green:#42ea92; }
    * { box-sizing:border-box; } body { margin:0; width:1440px; min-height:960px; overflow:hidden; background:var(--bg); color:var(--text); font:14px/1.4 Inter,ui-sans-serif,system-ui,sans-serif; }
    .profile { height:38px; padding:10px 18px; color:var(--amber); background:#2c2500; border-bottom:1px solid #675700; }
    .shell { display:grid; grid-template-columns:268px 1fr; min-height:922px; } aside { padding:22px 16px; border-right:1px solid var(--line); } .brand { font-size:19px; font-weight:800; letter-spacing:.12em; } nav { margin-top:30px; display:grid; gap:4px; } nav div { padding:9px 12px; color:var(--muted); font-size:11px; letter-spacing:.1em; text-transform:uppercase; } nav .active { color:var(--cream); background:#29413f; font-weight:800; }
    main { min-width:0; } header { height:86px; padding:24px 34px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); } h1,h2,h3,p { margin-top:0; } h1 { font-size:20px; letter-spacing:.08em; text-transform:uppercase; } .tabs { display:flex; } .tab { padding:11px 22px; border:1px solid var(--line); color:var(--muted); font-size:11px; letter-spacing:.1em; text-transform:uppercase; } .tab.active { color:var(--ink); background:var(--cream); border-color:var(--cream); font-weight:800; }
    .workspace { padding:24px 34px; } .crumb { color:var(--amber); font-size:11px; letter-spacing:.1em; text-transform:uppercase; } .intro { max-width:800px; color:var(--muted); } .card { max-width:1060px; padding:20px; border:1px solid var(--line); background:var(--panel); } .profiles { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:14px; } .profile-card { padding:14px; border:1px solid var(--line); background:var(--soft); } .profile-card h3 { margin-bottom:8px; } .facts { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:0 0 10px; } .facts span { display:block; color:var(--muted); font-size:10px; letter-spacing:.1em; text-transform:uppercase; } .facts b { display:block; margin-top:3px; color:var(--cream); } .field { display:grid; grid-template-columns:1fr 164px; gap:10px; margin:10px 0 0; } input,select { padding:11px; border:1px solid var(--line); background:#001a18; color:var(--cream); } button { border:1px solid var(--cream); background:var(--cream); color:var(--ink); font-weight:800; letter-spacing:.06em; text-transform:uppercase; } .hint { color:var(--muted); font-size:12px; }
    .preview { display:grid; grid-template-columns:1fr 1fr; gap:1px; margin-top:24px; border:1px solid var(--line); background:var(--line); } .preview section { min-height:168px; padding:18px; background:var(--soft); } .label { color:var(--muted); font-size:10px; letter-spacing:.11em; text-transform:uppercase; } .value { margin:5px 0 16px; color:var(--cream); font-size:17px; font-weight:700; } .ok { color:var(--green); } .warn { color:var(--amber); } code { color:var(--green); font-size:12px; } .confirm { margin-top:22px; padding:16px; border:1px solid var(--amber); background:#182c28; } .confirm label { display:block; margin-bottom:12px; color:var(--cream); } .confirm button { padding:12px 20px; } .note { margin-top:20px; max-width:1060px; padding:14px 16px; border:1px dashed #496763; color:var(--muted); } .annotation { position:fixed; right:14px; bottom:11px; color:#617b77; font-size:10px; }
  </style>
</head>
<body>
  <div class="profile">Every existing Hermes profile is listed with its registered repository and slug. No profile roots or secret metadata are exposed.</div>
  <div class="shell"><aside><div class="brand">HERMES<br>AGENT</div><nav><div>Chat</div><div>Sessions</div><div>Kanban</div><div>Skills</div><div>Plugins</div><div class="active">Daidala</div></nav></aside>
  <main><header><h1>Daidala</h1><div class="tabs"><div class="tab">Workflows</div><div class="tab">Artifacts</div><div class="tab active">Config</div></div></header>
    <section class="workspace"><p class="crumb">Config / GitHub Repositories</p><h2>Register a GitHub repository</h2><p class="intro">Every existing Hermes profile is visible at once. A registered row shows the repository and slug and prefills the GitHub link. Daidala inspects committed policy before it writes exactly two non-secret profile-local records.</p>
      <section class="card"><h3>Profile inventory</h3>
        <div class="profiles">
          <article class="profile-card"><h3>demo-controller</h3><div class="facts"><div><span>Repository</span><b>acme/payments-service</b></div><div><span>Slug</span><b>acme-payments-service</b></div></div><div class="field"><input value="github.com/acme/payments-service" aria-label="GitHub repository link for demo-controller"><button>Inspect repository</button></div><p class="hint">Register another repository</p><div class="field"><input placeholder="github.com/owner/repository" aria-label="Register another repository for demo-controller"><button>Inspect repository</button></div></article>
          <article class="profile-card"><h3>daidala-self-improvement</h3><p class="hint">No repository registered</p><div class="field"><input placeholder="github.com/owner/repository" aria-label="GitHub repository link for daidala-self-improvement"><button>Inspect repository</button></div></article>
        </div>
        <div class="preview"><section><p class="label">Repository identity</p><p class="value">acme/payments-service</p><p class="label">Project ID</p><p class="value">acme-payments-service</p><p class="label">Manifest digest</p><code>6f12…9c80</code></section><section><p class="label">Selected controller readiness</p><p class="ok">✓ Board selected</p><p class="ok">✓ Attended target configured</p><p class="warn">! Credential not available</p><p class="hint">Credential readiness does not grant commit or push authority.</p></section></div>
        <div class="confirm"><label><input type="checkbox"> I confirm registering acme/payments-service for profile demo-controller. This writes two non-secret profile-local records.</label><button>Register repository</button></div>
      </section><p class="note">Registration does not commit, push, create a GitHub Project, store a token, or create delivery authority. The release policy remains commit off · push off · publish off.</p>
    </section></main></div><div class="annotation">Static capability wireframe · synthetic data · no runtime authority</div>
</body></html>`;
}

function buildReviewedBranchDeliveryHtml(screen) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${screen.capability} — ${screen.title}</title>
  <style>
    :root { color-scheme: dark; --bg:#001f1d; --panel:#032725; --soft:#082f2c; --line:#244845; --text:#f4ead8; --muted:#8fa6a1; --cream:#ffe6ca; --ink:#102321; --amber:#ffc933; --green:#42ea92; }
    * { box-sizing:border-box; } body { margin:0; width:1440px; min-height:960px; overflow:hidden; background:var(--bg); color:var(--text); font:14px/1.4 Inter,ui-sans-serif,system-ui,sans-serif; }
    .profile { height:38px; padding:10px 18px; color:var(--amber); background:#2c2500; border-bottom:1px solid #675700; } .shell { display:grid; grid-template-columns:268px 1fr; min-height:922px; } aside { padding:22px 16px; border-right:1px solid var(--line); } .brand { font-size:19px; font-weight:800; letter-spacing:.12em; } nav { margin-top:30px; display:grid; gap:4px; } nav div { padding:9px 12px; color:var(--muted); font-size:11px; letter-spacing:.1em; text-transform:uppercase; } nav .active { color:var(--cream); background:#29413f; font-weight:800; }
    main { min-width:0; } header { height:86px; padding:24px 34px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); } h1,h2,h3,p { margin-top:0; } h1 { font-size:20px; letter-spacing:.08em; text-transform:uppercase; } .tabs { display:flex; } .tab { padding:11px 22px; border:1px solid var(--line); color:var(--muted); font-size:11px; letter-spacing:.1em; text-transform:uppercase; } .tab.active { color:var(--ink); background:var(--cream); border-color:var(--cream); font-weight:800; }
    .workspace { padding:28px 34px; } .crumb { color:var(--amber); font-size:11px; letter-spacing:.1em; text-transform:uppercase; } .intro { max-width:860px; color:var(--muted); } .card { max-width:1080px; padding:23px; border:1px solid var(--line); background:var(--panel); } .status { display:flex; gap:12px; align-items:center; margin-bottom:18px; padding:11px 13px; border:1px solid var(--green); background:#06372f; } .status b { color:var(--green); font-size:11px; letter-spacing:.1em; text-transform:uppercase; }
    .facts { display:grid; grid-template-columns:1fr 1fr 1fr; gap:1px; border:1px solid var(--line); background:var(--line); } .facts section { min-height:116px; padding:15px; background:var(--soft); } .label { color:var(--muted); font-size:10px; letter-spacing:.11em; text-transform:uppercase; } .value { margin:5px 0 13px; color:var(--cream); font-size:16px; font-weight:700; overflow-wrap:anywhere; } code { color:var(--green); font-size:12px; } .paths { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:20px; } .paths ul { margin:7px 0 0; padding-left:20px; color:var(--cream); } .paths li { margin:5px 0; } .gate { padding:15px; border:1px solid var(--amber); background:#182c28; } .gate p { color:var(--muted); } label { display:block; margin:13px 0; color:var(--cream); } button { padding:12px 18px; border:1px solid var(--cream); background:var(--cream); color:var(--ink); font-weight:800; letter-spacing:.06em; text-transform:uppercase; } .note { margin-top:17px; max-width:1080px; padding:13px 16px; border:1px dashed #496763; color:var(--muted); } .annotation { position:fixed; right:14px; bottom:11px; color:#617b77; font-size:10px; }
  </style>
</head>
<body>
  <div class="profile">Managing profile “demo-controller” — branch delivery resolves authority only from this mounted Hermes profile.</div>
  <div class="shell"><aside><div class="brand">HERMES<br>AGENT</div><nav><div>Chat</div><div>Sessions</div><div>Kanban</div><div>Skills</div><div>Plugins</div><div class="active">Daidala</div></nav></aside>
  <main><header><h1>Daidala</h1><div class="tabs"><div class="tab active">Workflows</div><div class="tab">Artifacts</div><div class="tab">Config</div></div></header>
    <section class="workspace"><p class="crumb">Workflows / dependency-refresh-demo / delivery</p><h2>Reviewed branch delivery</h2><p class="intro">Inspect the fresh preview derived from accepted review evidence. Confirmation can commit and push only the displayed Daidala-owned branch.</p>
      <section class="card"><div class="status"><b>Ready for attended confirmation</b><span>Accepted review · release policy allows commit and push · delivery credential available</span></div><div class="facts"><section><p class="label">Target branch</p><p class="value">daidala/dependency-refresh-demo</p><p class="label">Baseline</p><code>47c4…ac91</code></section><section><p class="label">Review evidence</p><p class="value">Accepted review</p><p class="label">Review digest</p><code>7ba4…10d2</code></section><section><p class="label">Preview identity</p><p class="value">Fresh exact preview</p><p class="label">Preview digest</p><code>0a9f…cb31</code></section></div><div class="paths"><section><h3>Reviewed changed paths</h3><ul><li>daidala/delivery.py</li><li>tests/test_delivery.py</li><li>docs/07-runbook.md</li></ul></section><section class="gate"><h3>Commit and push boundary</h3><p>The browser neither supplies nor displays a credential. It cannot select a remote, branch, worktree, or changed path.</p><label><input type="checkbox"> I confirm committing and pushing this exact branch delivery.</label><button>Confirm commit and push branch</button></section></div></section><p class="note">The operation creates no pull request, merge, release, publication, or default-branch update. Completion records only branch and commit receipt, then releases the Daidala-owned worktree.</p>
    </section></main></div><div class="annotation">Static capability wireframe · synthetic data · no runtime authority</div>
</body></html>`;
}

function buildRepositoryPolicyBootstrapHtml(screen) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${screen.capability} — ${screen.title}</title>
  <style>
    :root { color-scheme: dark; --bg:#001f1d; --panel:#032725; --soft:#082f2c; --line:#244845; --text:#f4ead8; --muted:#8fa6a1; --cream:#ffe6ca; --ink:#102321; --amber:#ffc933; --green:#42ea92; }
    * { box-sizing:border-box; } body { margin:0; width:1440px; min-height:960px; overflow:hidden; background:var(--bg); color:var(--text); font:14px/1.4 Inter,ui-sans-serif,system-ui,sans-serif; }
    .profile { height:38px; padding:10px 18px; color:var(--amber); background:#2c2500; border-bottom:1px solid #675700; }
    .shell { display:grid; grid-template-columns:268px 1fr; min-height:922px; } aside { padding:22px 16px; border-right:1px solid var(--line); } .brand { font-size:19px; font-weight:800; letter-spacing:.12em; } nav { margin-top:30px; display:grid; gap:4px; } nav div { padding:9px 12px; color:var(--muted); font-size:11px; letter-spacing:.1em; text-transform:uppercase; } nav .active { color:var(--cream); background:#29413f; font-weight:800; }
    main { min-width:0; } header { height:86px; padding:24px 34px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); } h1,h2,h3,p { margin-top:0; } h1 { font-size:20px; letter-spacing:.08em; text-transform:uppercase; } .tabs { display:flex; } .tab { padding:11px 22px; border:1px solid var(--line); color:var(--muted); font-size:11px; letter-spacing:.1em; text-transform:uppercase; } .tab.active { color:var(--ink); background:var(--cream); border-color:var(--cream); font-weight:800; }
    .workspace { padding:32px 34px; } .crumb { color:var(--amber); font-size:11px; letter-spacing:.1em; text-transform:uppercase; } .intro { max-width:820px; color:var(--muted); } .card { max-width:1060px; padding:24px; border:1px solid var(--line); background:var(--panel); } .field { display:grid; grid-template-columns:1fr 164px; gap:10px; margin:20px 0 10px; } input,select { padding:13px; border:1px solid var(--line); background:#001a18; color:var(--cream); } button { border:1px solid var(--cream); background:var(--cream); color:var(--ink); font-weight:800; letter-spacing:.06em; text-transform:uppercase; } .hint { color:var(--muted); font-size:12px; }
    .preview { display:grid; grid-template-columns:1fr 1fr; gap:1px; margin-top:24px; border:1px solid var(--line); background:var(--line); } .preview section { min-height:168px; padding:18px; background:var(--soft); } .label { color:var(--muted); font-size:10px; letter-spacing:.11em; text-transform:uppercase; } .value { margin:5px 0 16px; color:var(--cream); font-size:17px; font-weight:700; } .ok { color:var(--green); } .warn { color:var(--amber); } code { color:var(--green); font-size:12px; } .confirm { margin-top:22px; padding:16px; border:1px solid var(--amber); background:#182c28; } .confirm label { display:block; margin-bottom:12px; color:var(--cream); } .confirm button { padding:12px 20px; } .note { margin-top:20px; max-width:1060px; padding:14px 16px; border:1px dashed #496763; color:var(--muted); } .annotation { position:fixed; right:14px; bottom:11px; color:#617b77; font-size:10px; }
  </style>
</head>
<body>
  <div class="profile">needs-bootstrap: committed project policy is missing. Bootstrap publishes branch-only policy.</div>
  <div class="shell"><aside><div class="brand">HERMES<br>AGENT</div><nav><div>Chat</div><div>Sessions</div><div>Kanban</div><div>Skills</div><div>Plugins</div><div class="active">Daidala</div></nav></aside>
  <main><header><h1>Daidala</h1><div class="tabs"><div class="tab">Workflows</div><div class="tab">Artifacts</div><div class="tab active">Config</div></div></header>
    <section class="workspace"><p class="crumb">Config / GitHub Repositories</p><h2>Bootstrap Daidala policy</h2><p class="intro">When a repository has no committed .daidala/project.yaml, publish conservative policy on branch chore/daidala-bootstrap-project-policy. Open the compare/PR link on GitHub to merge, then register.</p>
      <section class="card"><h3>Bootstrap preview</h3><p class="hint">Profile: demo-controller · Repository: acme/site · classification needs-bootstrap</p><div class="field"><input value="github.com/acme/site" aria-label="GitHub repository link for demo-controller"><button>Inspect repository</button></div>
        <div class="preview"><section><p class="label">Target branch</p><p class="value">chore/daidala-bootstrap-project-policy</p><p class="label">From default branch</p><p class="value">main</p><p class="label">Files</p><code>.daidala/project.yaml<br>.daidala/constraints.yaml</code></section><section><p class="label">Policy posture</p><p class="ok">✓ Release commit off</p><p class="ok">✓ Release push off</p><p class="warn">! No registration write</p><p class="hint">Host gh publishes the branch only. Links open branch, .daidala tree, and compare/PR.</p></section></div>
        <div class="confirm"><label><input type="checkbox"> I confirm publishing bootstrap policy on branch chore/daidala-bootstrap-project-policy</label><button>Bootstrap repository policy</button></div>
      </section><p class="note">Bootstrap does not register the repository, update the default branch, create a pull request via API, or store a token.</p>
    </section></main></div><div class="annotation">Static capability wireframe · synthetic data · no runtime authority</div>
</body></html>`;
}

function buildHtml(screen) {
  if (screen.capability === "CAP-0003") return buildOperatorDashboardHtml(screen);
  if (screen.capability === "CAP-0004") return buildRepositoryRegistrationHtml(screen);
  if (screen.capability === "CAP-0005") return buildReviewedBranchDeliveryHtml(screen);
  if (screen.capability === "CAP-0006") return buildRepositoryPolicyBootstrapHtml(screen);
  if (screen.capability === "CAP-0007") {
    return buildCompletePackInstallationProgressHtml(screen);
  }
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${screen.capability} — ${screen.title}</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #001f1d;
      --panel: #032725;
      --panel-soft: #082f2c;
      --line: #244845;
      --text: #f4ead8;
      --muted: #8fa6a1;
      --cream: #ffe6ca;
      --ink: #102321;
      --amber: #ffc933;
      --green: #42ea92;
      --red: #ff786f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      width: 1440px;
      min-height: 960px;
      overflow: hidden;
      background: var(--bg);
      color: var(--text);
      font: 13px/1.35 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: .01em;
    }
    button, select, input { font: inherit; }
    .profile-banner {
      height: 38px;
      display: flex;
      align-items: center;
      padding: 0 16px;
      color: var(--amber);
      background: #2c2500;
      border-bottom: 1px solid #675700;
    }
    .shell { display: grid; grid-template-columns: 344px 1fr; height: 922px; }
    .sidebar {
      border-right: 1px solid var(--line);
      padding: 16px 14px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .brand-row { display: flex; justify-content: space-between; align-items: center; }
    .brand { font-size: 18px; line-height: 1.02; letter-spacing: .08em; font-weight: 800; }
    .collapse { width: 36px; height: 36px; border: 1px solid var(--line); color: var(--cream); display: grid; place-items: center; }
    .profile {
      height: 36px;
      padding: 0 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border: 1px solid var(--amber);
      color: var(--muted);
    }
    .nav { display: grid; gap: 2px; }
    .nav-group { margin: 6px 0 2px; color: #667f7b; font-size: 11px; }
    .nav-item { padding: 3px 12px; color: #b8c4c0; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; }
    .nav-item.active { background: #29413f; color: var(--cream); font-weight: 800; }
    .system-card { margin-top: auto; padding: 11px; border: 1px solid var(--line); color: var(--muted); }
    .system-card strong { display: block; color: var(--green); font-weight: 500; margin-top: 4px; }
    .system-card small { display: block; margin-top: 8px; }
    .main { min-width: 0; }
    .topbar {
      height: 74px;
      padding: 18px 32px;
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      border-bottom: 1px solid var(--line);
    }
    h1 { margin: 0; font-size: 17px; letter-spacing: .12em; text-transform: uppercase; }
    h1 span { display: inline-block; margin-left: 10px; padding: 4px 11px; border: 1px solid var(--line); font-size: 11px; font-weight: 500; }
    .tabs { display: flex; height: 38px; }
    .tab { min-width: 118px; padding: 0 22px; border: 1px solid var(--line); display: grid; place-items: center; color: #c4c3b8; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; }
    .tab.active { color: var(--ink); background: var(--cream); border-color: var(--cream); font-weight: 800; }
    .workspace { padding: 24px 32px; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); border: 1px solid var(--line); }
    .stat { min-height: 48px; padding: 8px 12px; }
    .stat b { display: block; font-size: 16px; }
    .stat small { color: var(--muted); }
    .stat.active b { color: var(--green); }
    .stat.attention b { color: var(--amber); }
    .filters { display: grid; grid-template-columns: 210px 210px 1fr 150px; gap: 8px; margin: 8px 0; }
    .field { min-height: 42px; padding: 7px 9px; border: 1px solid var(--line); }
    .field label { display: block; color: #a2aaa4; font-size: 9px; letter-spacing: .08em; text-transform: uppercase; }
    .field span { color: var(--muted); }
    .button { border: 1px solid var(--line); display: grid; place-items: center; color: var(--text); font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
    .button.primary { background: var(--cream); border-color: var(--cream); color: var(--ink); }
    .guidance { display: grid; grid-template-columns: 1fr 300px; gap: 12px; margin: 10px 0 14px; padding: 10px 12px; border: 1px solid #496763; background: var(--panel-soft); }
    .guidance b { display: block; color: var(--cream); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
    .guidance p { margin: 3px 0 0; color: var(--muted); font-size: 11px; }
    .advice { padding-left: 12px; border-left: 1px solid var(--line); }
    .advice .button { height: 25px; width: 178px; margin-top: 7px; color: var(--cream); }
    .section-title { margin: 10px 0 6px; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
    .attention-card { border: 1px solid var(--amber); border-radius: 7px; overflow: hidden; }
    .attention-row, .run-row, .finished-row {
      min-height: 51px;
      padding: 9px 12px;
      display: grid;
      align-items: center;
      gap: 8px;
      border-bottom: 1px solid var(--line);
    }
    .attention-row { grid-template-columns: 1fr 150px 132px; }
    .attention-row:last-child, .finished-row:last-child { border-bottom: 0; }
    .identity { font-weight: 700; color: #c9c0ac; }
    .identity small { display: block; margin-top: 3px; color: var(--muted); font-weight: 400; }
    .badge { min-width: 124px; padding: 5px 8px; border: 1px solid currentColor; border-radius: 5px; text-align: center; font-size: 9px; font-weight: 800; text-transform: uppercase; }
    .badge.amber { color: var(--amber); }
    .badge.green { color: var(--green); }
    .run-card, .finished-card { border: 1px solid var(--line); border-radius: 7px; overflow: hidden; }
    .run-row { min-height: 78px; grid-template-columns: 1fr 116px; }
    .stage-line { display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; margin-top: 10px; }
    .stage { min-height: 31px; padding: 8px; border: 1px solid var(--line); color: var(--muted); text-align: center; font-size: 9px; text-transform: uppercase; }
    .stage.done { border-color: var(--green); color: var(--green); }
    .stage.current { border-color: var(--green); color: var(--green); background: #06372f; }
    .finished-row { grid-template-columns: 1fr 120px 90px; }
    .open { color: var(--cream); text-align: right; font-size: 10px; font-weight: 800; }
    .state-note { margin-top: 12px; padding: 10px 12px; border: 1px dashed #496763; color: var(--muted); display: flex; justify-content: space-between; }
    .state-note b { color: var(--text); }
    .annotation { position: fixed; right: 14px; bottom: 11px; color: #617b77; font-size: 10px; }
  </style>
</head>
<body>
  <div class="profile-banner">Managing profile “demo-controller” — configuration and new workflow requests apply to that profile.</div>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand-row"><div class="brand">HERMES<br>AGENT</div><div class="collapse">◀</div></div>
      <div class="profile"><span>demo-controller</span><span>⌄</span></div>
      <nav class="nav" aria-label="Hermes navigation">
        <div class="nav-item">Chat</div><div class="nav-item">Sessions</div><div class="nav-item">Files</div>
        <div class="nav-item">Models</div><div class="nav-item">Logs</div><div class="nav-item">Cron</div>
        <div class="nav-item">Skills</div><div class="nav-item">Plugins</div><div class="nav-item">MCP</div>
        <div class="nav-item">Channels</div><div class="nav-item">Webhooks</div><div class="nav-item">Pairing</div>
        <div class="nav-item">Profiles</div><div class="nav-item">Config</div><div class="nav-item">Keys</div>
        <div class="nav-item">System</div><div class="nav-item">Documentation</div>
        <div class="nav-group">Plugins</div><div class="nav-item">Kanban</div><div class="nav-item">Achievements</div>
        <div class="nav-item active">Daidala</div>
      </nav>
      <div class="system-card">System<strong>Gateway status: Running</strong><strong>Active sessions: 0</strong><small>HERMES · DEMO PROFILE</small></div>
    </aside>
    <main class="main">
      <header class="topbar">
        <h1>Workflows <span>18</span></h1>
        <div class="tabs" role="tablist"><div class="tab active">Workflows</div><div class="tab">Artifacts</div><div class="tab">Config</div></div>
      </header>
      <section class="workspace">
        <div class="stats"><div class="stat active"><b>1</b><small>Active</small></div><div class="stat attention"><b>2</b><small>Awaiting action</small></div><div class="stat"><b>14</b><small>Completed</small></div><div class="stat"><b>1</b><small>Cancelled</small></div></div>
        <div class="filters"><div class="field"><label>Status</label><span>All states</span></div><div class="field"><label>Pack</label><span>All packs</span></div><div class="field"><label>Search</label><span>workflow ID or outcome</span></div><div class="button primary">Start workflow</div></div>
        <section class="guidance"><div><b>Workflow supervision</b><p>Use Workflows to inspect approval-gated progress and make the next required human decision from source-bound evidence.</p></div><div class="advice"><b>Readiness advice</b><p>One-off path-free guidance; advisory only.</p><div class="button">Analyze Daidala readiness</div><p><b>Resolve blocked workflow packs</b></p><div class="button">Open Config → Packs</div></div></section>

        <h2 class="section-title">Awaiting action · open the workflow to decide</h2>
        <div class="attention-card">
          <div class="attention-row"><div class="identity">api-hardening-demo<small>Next — Review 2 findings, add feedback, then preview plan revision 2.</small></div><div class="badge amber">● Changes requested</div><div class="button primary">Request revision</div></div>
          <div class="attention-row"><div class="identity">calculator-regression-demo<small>Next — Review the exact plan and digest before implementation starts.</small></div><div class="badge amber">● Plan approval</div><div class="button">Review plan</div></div>
        </div>

        <h2 class="section-title">Active · running without operator input</h2>
        <div class="run-card"><div class="run-row"><div><div class="identity">dependency-refresh-demo · addyosmani · demo-worker</div><div class="stage-line"><div class="stage done">Define · done</div><div class="stage done">Plan · done</div><div class="stage current">Implement · running</div><div class="stage">Verify · queued</div><div class="stage">Review · queued</div></div></div><div><div class="badge green">● Running</div><div class="button" style="height:31px;margin-top:8px">Open details</div></div></div></div>

        <h2 class="section-title">Recently finished workflows · latest 5</h2>
        <div class="finished-card"><div class="finished-row"><div class="identity">api-hardening-complete<small>completed 2h ago · 7 verified artifacts · delivery not committed or pushed</small></div><div class="badge green">● Completed</div><div class="open">Open →</div></div><div class="finished-row"><div class="identity">calculator-regression-complete<small>completed yesterday · 6 verified artifacts · accepted review</small></div><div class="badge green">● Completed</div><div class="open">Open →</div></div></div>

        <div class="state-note"><span><b>Empty result:</b> Clear filters or start a workflow.</span><span><b>Host unavailable:</b> Keep the last safe snapshot and retry manually.</span></div>
      </section>
    </main>
  </div>
  <div class="annotation">Static capability wireframe · synthetic data · no runtime authority</div>
</body>
</html>
`;
}

function buildIndex(screens) {
  const entries = screens
    .map(
      (screen) =>
        `<h2>${screen.capability} — ${screen.title}</h2><p><a href="${screen.html}">Open interactive HTML</a> · <a href="${screen.png}">Open PNG export</a></p><a href="${screen.html}"><img src="${screen.png}" alt="${screen.title} wireframe"></a><p><code>${screen.viewport.width} × ${screen.viewport.height}</code></p>`,
    )
    .join("");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Daidala capability wireframes</title><style>body{max-width:900px;margin:48px auto;padding:0 24px;background:#001f1d;color:#f4ead8;font:16px/1.5 system-ui}a{color:#ffc933}img{max-width:100%;border:1px solid #244845}code{color:#42ea92}</style></head><body><h1>Daidala capability wireframes</h1><p>Static visual references only. Runtime source and executable tests remain behavior authority.</p>${entries}</body></html>
`;
}

mkdirSync(join(ROOT, "html"), { recursive: true });
mkdirSync(join(ROOT, "exports"), { recursive: true });
for (const screen of SCREENS) {
  writeFileSync(join(ROOT, screen.html), buildHtml(screen), "utf8");
}
writeFileSync(join(ROOT, "index.html"), buildIndex(SCREENS), "utf8");
writeFileSync(
  join(ROOT, "manifest.json"),
  `${JSON.stringify({ version: 1, screens: SCREENS }, null, 2)}\n`,
  "utf8",
);

if (process.argv.includes("--render")) {
  const pathEntries = (process.env.PATH || "").split(":");
  const browser = [
    process.env.CHROME_BIN,
    ...["google-chrome", "chromium", "chromium-browser"].flatMap((name) =>
      pathEntries.map((directory) => join(directory, name)),
    ),
  ].find((candidate) => candidate && existsSync(candidate));
  if (!browser) {
    throw new Error("No supported Chrome/Chromium binary found; set CHROME_BIN");
  }
  const profile = mkdtempSync(join(tmpdir(), "daidala-wireframe-"));
  try {
    for (const screen of SCREENS) {
      const result = spawnSync(
        browser,
        [
          "--headless=new",
          "--disable-gpu",
          "--no-sandbox",
          "--hide-scrollbars",
          `--user-data-dir=${profile}`,
          `--window-size=${screen.viewport.width},${screen.viewport.height}`,
          `--screenshot=${join(ROOT, screen.png)}`,
          `file://${join(ROOT, screen.html)}`,
        ],
        { encoding: "utf8" },
      );
      if (result.status !== 0) {
        throw new Error(result.stderr || `Chrome exited ${result.status}`);
      }
    }
  } finally {
    rmSync(profile, { recursive: true, force: true });
  }
}

const generatedHtml = SCREENS.map((screen) => screen.html).join(", ");
const generatedPng = SCREENS.map((screen) => screen.png).join(", ");
console.log(`Generated ${generatedHtml}, index.html, manifest.json${process.argv.includes("--render") ? `, and ${generatedPng}` : ""}.`);
