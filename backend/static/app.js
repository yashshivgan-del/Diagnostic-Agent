// Predictive Diagnostic Assistant - live dashboard (no framework, no build step).
// Talks only to the backend: REST for actions/snapshots, Server-Sent Events for live updates.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 2) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "-" : Number(v).toFixed(d));
const hhmmss = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour12: false }) : "-");
const pretty = (s) => (s ? String(s).replace(/_/g, " ") : "-");
const arr = (v) => (Array.isArray(v) ? v : v === null || v === undefined || v === "" ? [] : [String(v)]);

// Runs started in this browser: { run_id: access_token }. Only this browser can view/control them.
const STORE_KEY = "pda_runs";
function myRuns() { try { return JSON.parse(localStorage.getItem(STORE_KEY) || "{}"); } catch { return {}; } }
function saveRun(id, token) { try { const m = myRuns(); m[id] = token; localStorage.setItem(STORE_KEY, JSON.stringify(m)); } catch { /* private mode */ } }
const tokenFor = (id) => myRuns()[id] || sessionTokens[id] || null;
const sessionTokens = {};   // fallback when localStorage is unavailable

// This student's Karini recipe creds, remembered in this browser and prefilled on the next Start.
const KARINI_KEY = "pda_karini";
function myKarini() { try { return JSON.parse(localStorage.getItem(KARINI_KEY) || "{}"); } catch { return {}; } }
function saveKarini(c) { try { localStorage.setItem(KARINI_KEY, JSON.stringify(c)); } catch { /* private mode */ } }

const SENSORS = [
  ["temperature_c", "Bearing temp", "°C", [57, 68], 1],
  ["vibration_mm_s", "Vibration", "mm/s", [1.6, 3.3], 2],
  ["discharge_pressure_bar", "Discharge pressure", "bar", [5.7, 6.35], 2],
  ["flow_m3h", "Flow", "m³/h", [112, 128], 1],
  ["motor_current_a", "Motor current", "A", [39, 44.5], 1],
  ["rpm", "Speed", "rpm", [1468, 1495], 0],
];
const STRENGTH = { low: 33, medium: 66, high: 100 };

const state = { cfg: null, runId: null, run: null, readings: [], byEvent: new Map(), logs: [],
                 execs: new Map(), traces: new Map(), reports: new Map(), es: null, open: new Set(),
                 dirty: new Set(), raf: 0, timer: 0, resync: false };

// ----------------------------------------------------------------------------- api
async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
  let body = null;
  try { body = await r.json(); } catch { /* empty */ }
  if (!r.ok) throw new Error((body && body.error) || `HTTP ${r.status}`);
  return body;
}
function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

// ----------------------------------------------------------------------------- routing
function navigate(path) { history.pushState({}, "", path); route(); }
window.addEventListener("popstate", route);
document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-nav]");
  if (a) { e.preventDefault(); navigate(a.dataset.nav); }
  if (e.target.closest("[data-action=start]")) openStart();
});
function route() {
  closeStream();
  clearInterval(state.timer);
  const m = location.pathname.match(/^\/run\/([0-9a-f-]{36})/i);
  if (m) openRun(m[1]); else openHome();
}

// ----------------------------------------------------------------------------- home
async function openHome() {
  $("#view").replaceChildren($("#tplHome").content.cloneNode(true));
  try {
    const runs = await api("/api/runs/history", { method: "POST", body: JSON.stringify({ runs: myRuns() }) });
    $("#runsBody").innerHTML = runs.length ? runs.map((r) => `
      <tr data-nav="/run/${r.run_id}">
        <td>${esc(new Date(r.started_at).toLocaleString())}</td><td>${esc(r.label || "-")}</td>
        <td class="mono small">${esc(r.email_masked)}</td><td><span class="pill ${esc(r.status)}">${esc(pretty(r.status))}</span></td>
        <td>${r.readings}</td><td>${r.executions}</td><td>${r.reports}</td></tr>`).join("")
      : `<tr><td colspan="7" class="muted">No runs from this browser yet. Press Start run.</td></tr>`;
  } catch (e) { $("#runsBody").innerHTML = `<tr><td colspan="7">${esc(e.message)}</td></tr>`; }
}

// ----------------------------------------------------------------------------- start dialog
function openStart() {
  $("#fError").textContent = "";
  const k = myKarini();
  $("#fKBase").value = k.base_url || "";
  $("#fKRecipe").value = k.recipe_id || "";
  $("#fKToken").value = k.api_token || "";
  if (k.recipe_id || k.api_token) $("#kariniBox").open = true;
  $("#startDialog").showModal();
  setTimeout(() => $("#fEmail").focus(), 30);
}
$("#btnStartTop").addEventListener("click", openStart);
$("#btnCancel").addEventListener("click", () => $("#startDialog").close());
$("#startForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = $("#fEmail").value.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) { $("#fError").textContent = "Please enter a valid email address."; return; }
  const karini = { base_url: $("#fKBase").value.trim(), recipe_id: $("#fKRecipe").value.trim(), api_token: $("#fKToken").value.trim() };
  const kGiven = [karini.base_url, karini.recipe_id, karini.api_token].filter(Boolean);
  if (kGiven.length && kGiven.length !== 3) {
    $("#fError").textContent = "To use your own recipe, fill the base URL, recipe ID and API token (or clear all three).";
    $("#kariniBox").open = true; return;
  }
  $("#btnStart").disabled = true;
  try {
    const body = { email, label: $("#fLabel").value.trim() || null };
    if (kGiven.length === 3) body.karini = karini;
    const run = await api("/api/runs", { method: "POST", body: JSON.stringify(body) });
    if (kGiven.length === 3) saveKarini(karini);   // remember for next Start in this browser
    sessionTokens[run.run_id] = run.access_token;
    saveRun(run.run_id, run.access_token);
    $("#startDialog").close();
    navigate(`/run/${run.run_id}`);
  } catch (err) { $("#fError").textContent = err.message; }
  finally { $("#btnStart").disabled = false; }
});

// ----------------------------------------------------------------------------- run view
async function openRun(id) {
  if (!tokenFor(id)) {
    $("#view").innerHTML = `<section class="card"><h2>Run not available in this browser</h2>
      <p class="muted">A run's live data is visible only in the browser that started it.</p>
      <button class="btn primary" data-action="start">Start a new run</button></section>`;
    return;
  }
  $("#view").replaceChildren($("#tplRun").content.cloneNode(true));
  Object.assign(state, { runId: id, run: null, readings: [], byEvent: new Map(), logs: [], execs: new Map(),
                         traces: new Map(), reports: new Map(), open: new Set() });
  $("#btnInject").addEventListener("click", inject);
  $("#btnStop").addEventListener("click", stopRun);
  $("#timeline").addEventListener("toggle", (e) => {
    const d = e.target; if (!d.dataset || !d.dataset.key) return;
    d.open ? state.open.add(d.dataset.key) : state.open.delete(d.dataset.key);
  }, true);
  try { await loadSnapshot(); } catch (e) { $("#view").innerHTML = `<p class="card">${esc(e.message)}</p>`; return; }
  openStream();
  state.timer = setInterval(renderCountdown, 1000);
}

async function loadSnapshot() {
  const s = await api(`/api/runs/${state.runId}`, { headers: { "x-run-token": tokenFor(state.runId) } });
  state.run = s.run;
  state.readings = s.readings; state.byEvent = new Map(s.readings.map((r) => [r.event_id, r]));
  state.logs = s.logs;
  state.execs = new Map(s.executions.map((x) => [x.event_id, x]));
  state.traces = new Map(s.traces.map((t) => [t.trace_id, t]));
  state.reports = new Map(s.reports.map((r) => [r.event_id, r]));
  markDirty("all");
}

function openStream() {
  closeStream();
  const es = new EventSource(`/api/runs/${state.runId}/stream?t=${encodeURIComponent(tokenFor(state.runId))}`);
  state.es = es;
  es.addEventListener("hello", () => { if (state.resync) { state.resync = false; loadSnapshot(); } });
  es.addEventListener("error", () => { state.resync = true; });
  es.addEventListener("resync", () => loadSnapshot());
  es.addEventListener("reading", (e) => {
    const r = JSON.parse(e.data);
    if (!state.byEvent.has(r.event_id)) { state.readings.push(r); state.readings.sort((a, b) => a.seq - b.seq); }
    else Object.assign(state.byEvent.get(r.event_id), r);
    state.byEvent.set(r.event_id, state.byEvent.get(r.event_id) || r);
    const newLogs = (r.logs || []).map((l) => ({ ...l, event_id: r.event_id, fresh: true }));
    state.logs = newLogs.reverse().concat(state.logs).slice(0, 400);
    if (state.run) state.run.readings_seen = state.readings.length;
    markDirty("readings", "logs", "bar");
  });
  es.addEventListener("execution", (e) => { const x = JSON.parse(e.data); state.execs.set(x.event_id, x); markDirty("timeline", "bar"); });
  es.addEventListener("trace", (e) => { const t = JSON.parse(e.data); state.traces.set(t.trace_id, t); markDirty("timeline"); });
  es.addEventListener("report", (e) => { const r = JSON.parse(e.data); state.reports.set(r.event_id, r); markDirty("timeline"); });
  es.addEventListener("truth", (e) => {
    const t = JSON.parse(e.data); const r = state.byEvent.get(t.event_id); if (r) r.ground_truth = t.ground_truth; markDirty("timeline");
  });
  es.addEventListener("run", (e) => { state.run = { ...state.run, ...JSON.parse(e.data) }; markDirty("bar"); if (state.run.status !== "running") loadSnapshot(); });
}
function closeStream() { if (state.es) { state.es.close(); state.es = null; } }

async function inject() {
  try { await api(`/api/runs/${state.runId}/inject`, { method: "POST", headers: { "x-run-token": tokenFor(state.runId) } }); toast("Fault injected: it starts on the next reading."); }
  catch (e) { toast(e.message); }
}
async function stopRun() {
  try { await api(`/api/runs/${state.runId}/stop`, { method: "POST", headers: { "x-run-token": tokenFor(state.runId) } }); toast("Stopping. Agent runs already started will still finish."); }
  catch (e) { toast(e.message); }
}

// ----------------------------------------------------------------------------- rendering scheduler
function markDirty(...parts) {
  parts.forEach((p) => state.dirty.add(p));
  if (!state.raf) state.raf = requestAnimationFrame(flush);
}
function flush() {
  state.raf = 0;
  const d = state.dirty; state.dirty = new Set();
  const all = d.has("all");
  if (all || d.has("bar")) renderBar();
  if (all || d.has("readings")) { renderTiles(); renderScore(); }
  if (all || d.has("logs")) renderLogs();
  if (all || d.has("timeline") || d.has("readings")) renderTimeline();
}

function renderBar() {
  const r = state.run; if (!r || !$("#runStatus")) return;
  $("#runStatus").className = `pill ${r.status}`;
  $("#runStatus").textContent = pretty(r.status);
  $("#runTitle").textContent = `${r.label || "Run"} · ${r.machine_id} · ${r.email_masked}`;
  $("#runId").textContent = r.run_id;
  $("#runReadings").textContent = state.readings.length;
  $("#runTriggers").textContent = `${r.trigger_count}`;
  $("#runEmails").textContent = `${r.emails_sent} / ${r.email_cap}`;
  $("#runMode").innerHTML = r.inference_mode === "synthetic"
    ? `<span class="tag warn" title="Synthetic demo score, not an ML prediction">synthetic</span>` : `<span class="tag ok">SageMaker</span>`;
  const running = r.status === "running";
  $("#btnInject").disabled = !running; $("#btnStop").disabled = !running;
  const n = $("#runNotice");
  if (!running) { n.hidden = false; n.textContent = `Run ${pretty(r.status)}${r.stop_reason ? ` (${r.stop_reason})` : ""}. Agent runs already started still update here.`; }
  else n.hidden = true;
  renderCountdown();
}
function renderCountdown() {
  const r = state.run; const el = $("#runCountdown"); if (!r || !el) return;
  if (r.status !== "running") { el.textContent = "-"; return; }
  const s = Math.max(0, Math.round((new Date(r.auto_stop_at) - Date.now()) / 1000));
  el.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// ----------------------------------------------------------------------------- telemetry tiles
function spark(values, lo, hi) {
  if (!values.length) return "";
  const W = 120, H = 34;
  const min = Math.min(lo, ...values), max = Math.max(hi, ...values), pad = (max - min) * 0.1 || 1;
  const y = (v) => H - ((v - (min - pad)) / (max - min + 2 * pad)) * H;
  const x = (i) => (values.length === 1 ? W : (i / (values.length - 1)) * W);
  const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <rect x="0" y="${y(hi).toFixed(1)}" width="${W}" height="${(y(lo) - y(hi)).toFixed(1)}" fill="var(--band)"/>
    <polyline points="${pts}" fill="none" stroke="var(--chart-line)" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`;
}
function renderTiles() {
  const el = $("#tiles"); if (!el) return;
  const last = state.readings.slice(-60);
  const cur = last.length ? last[last.length - 1].telemetry : null;
  el.innerHTML = SENSORS.map(([k, name, unit, [lo, hi], dp]) => {
    const v = cur ? cur[k] : null; const out = v !== null && (v < lo || v > hi);
    return `<div class="tile ${out ? "out" : ""}"><div class="tile-name">${name}</div>
      <div class="tile-value">${num(v, dp)}<small>${unit}</small></div>${spark(last.map((r) => r.telemetry[k]), lo, hi)}</div>`;
  }).join("");
}

// ----------------------------------------------------------------------------- score chart
function renderScore() {
  const el = $("#scoreChart"); if (!el) return;
  const rs = state.readings; const th = state.run ? state.run.threshold : 2.5;
  const W = 600, H = 210, L = 32, R = 10, T = 10, B = 22;
  const perMin = Math.max(1, Math.round(60 / ((state.cfg && state.cfg.sim_interval_s) || 10)));
  const runReadings = Math.round(((state.cfg && state.cfg.run_max_seconds) || 600) / ((state.cfg && state.cfg.sim_interval_s) || 10));
  const maxSeq = Math.max(runReadings, ...rs.map((r) => r.seq));
  const scores = rs.filter((r) => r.anomaly_score !== null).map((r) => r.anomaly_score);
  const ymax = Math.max(th * 1.8, 5, ...scores.map((s) => s * 1.1));
  const x = (s) => L + ((s - 1) / Math.max(1, maxSeq - 1)) * (W - L - R);
  const y = (v) => T + (1 - v / ymax) * (H - T - B);
  let path = "", pen = false;
  rs.forEach((r) => { if (r.anomaly_score === null) { pen = false; return; } path += `${pen ? "L" : "M"}${x(r.seq).toFixed(1)},${y(r.anomaly_score).toFixed(1)}`; pen = true; });
  const yTicks = [0, ymax / 2, ymax].map((v) => `<text x="${L - 4}" y="${y(v) + 3}" text-anchor="end">${v.toFixed(1)}</text>
     <line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/>`).join("");
  let xTicks = "";
  const step = Math.max(1, Math.ceil(maxSeq / perMin / 6));
  for (let m = 0; m <= Math.ceil(maxSeq / perMin); m += step) {
    const s = m * perMin + 1; if (s > maxSeq) break;
    xTicks += `<text x="${x(s)}" y="${H - 6}" text-anchor="middle">${m}m</text>`;
  }
  const dots = rs.filter((r) => r.is_anomaly).map((r) => `<circle cx="${x(r.seq)}" cy="${y(r.anomaly_score)}" r="3" fill="var(--chart-th)"><title>reading ${r.seq}: ${num(r.anomaly_score)}</title></circle>`).join("");
  const trg = rs.filter((r) => r.trigger_decision === "triggered").map((r) => {
    const cx = x(r.seq), cy = y(r.anomaly_score);
    return `<rect x="${cx - 5}" y="${cy - 5}" width="10" height="10" transform="rotate(45 ${cx} ${cy})" fill="var(--chart-th)" stroke="var(--panel)" stroke-width="1.5"><title>agents triggered (reading ${r.seq})</title></rect>`;
  }).join("");
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Anomaly score over time">
    ${yTicks}${xTicks}
    <line x1="${L}" x2="${W - R}" y1="${y(th)}" y2="${y(th)}" stroke="var(--chart-th)" stroke-dasharray="5 4" stroke-width="1.5"/>
    <text x="${W - R}" y="${y(th) - 4}" text-anchor="end">threshold ${th}</text>
    <path d="${path}" fill="none" stroke="var(--chart-line)" stroke-width="2"/>${dots}${trg}</svg>`;
  const last = rs[rs.length - 1];
  $("#latest").innerHTML = last ? `
    <span>Reading <b>#${last.seq}</b> at ${hhmmss(last.ts)}</span>
    <span>Score <b>${num(last.anomaly_score)}</b> / ${num(last.threshold, 1)}</span>
    <span>${last.inference_status !== "ok" ? `<span class="tag bad">inference failed</span>` : last.is_anomaly ? `<span class="tag bad">anomaly</span>` : `<span class="tag ok">normal</span>`}</span>
    <span>Model class <b>${esc(pretty(last.predicted_fault))}</b></span>
    <span class="muted">${esc(decisionText(last.trigger_decision))}</span>` : `<span class="muted">Waiting for the first reading...</span>`;
}
function decisionText(d) {
  return ({ normal: "below threshold", anomaly_unconfirmed: "anomaly, waiting for confirmation (2 of 3)", triggered: "confirmed: agents triggered",
            suppressed_not_rearmed: "same episode: agents already triggered", suppressed_trigger_cap: "trigger cap reached",
            inference_failed: "inference failed: no decision", karini_disabled: "Karini disabled" })[d] || d;
}

// ----------------------------------------------------------------------------- logs
function renderLogs() {
  const el = $("#logs"); if (!el) return;
  el.innerHTML = state.logs.slice(0, 250).map((l) => `<li class="${l.fresh ? "new" : ""}"><span class="muted">${hhmmss(l.ts)}</span>
    <span class="lv-${esc(l.log_level)}">${esc(l.log_level)}</span><span class="code">${esc(l.event_code)}</span><span>${esc(l.message)}</span></li>`).join("")
    || `<li class="muted">No log lines yet.</li>`;
  state.logs.forEach((l) => { l.fresh = false; });
}

// ----------------------------------------------------------------------------- agent timeline
function tracesFor(eid) { return [...state.traces.values()].filter((t) => t.event_id === eid).sort((a, b) => a.trace_id - b.trace_id); }
function outputOf(ts, agent) { const t = ts.find((x) => x.kind === "output" && x.agent === agent); return t ? t.response : null; }

function stagesFor(x, ts, rep) {
  const finished = ["success", "failed", "timed_out", "post_failed"].includes(x.status);
  const a1 = outputOf(ts, "evidence_gatherer"), a2 = outputOf(ts, "diagnostic_reporter");
  const a1calls = ts.some((t) => t.agent === "evidence_gatherer");
  const st = (done, active, fail, skip) => (done ? "done" : fail ? "fail" : skip ? "skip" : active ? "active" : "");
  const webhookDone = ["accepted", "success", "failed", "timed_out"].includes(x.status);
  return [
    ["Confirmed", "done"],
    ["Webhook", st(webhookDone, ["queued", "posting"].includes(x.status), x.status === "post_failed")],
    ["Evidence", st(!!a1, webhookDone && !finished || a1calls, finished && !a1)],
    ["Diagnosis & report", st(!!rep, (!!a1 || !!a2) && !finished, finished && !rep)],
    ["Email", st(rep && rep.email_status === "submitted", rep && rep.email_status === "pending" && !finished,
                 rep && (rep.email_status === "failed" || (rep.email_status === "pending" && finished)), rep && rep.email_status === "skipped_cap")],
    ["Recipe", st(x.status === "success", x.status === "accepted", ["failed", "timed_out", "post_failed"].includes(x.status))],
  ];
}
function detailsBlock(eid, key, title, html, badge = "") {
  const k = `${eid}:${key}`;
  return `<details data-key="${k}" ${state.open.has(k) ? "open" : ""}><summary>${esc(title)}<span class="muted small">${esc(badge)}</span></summary><div class="body">${html}</div></details>`;
}
function renderEvidence(a1) {
  if (!a1) return `<p class="muted">Waiting for the Evidence Gatherer...</p>`;
  const refs = arr(a1.kb_refs).filter((r) => r && typeof r === "object").map((r) => `<li><b>${esc(r.doc_id)}</b> ${esc(r.title || "")} <span class="muted">${esc(r.relevance || r.type || "")}</span></li>`).join("");
  const logs = arr(a1.logs).filter((l) => l && typeof l === "object").slice(0, 8).map((l) => `<li class="mono small">${esc(l.event_code)} ${esc(l.message)}</li>`).join("");
  return `<dl class="kv"><dt>Evidence</dt><dd><span class="tag">${esc(a1.evidence_status || "-")}</span> ${esc(a1.summary || a1.event_summary || "")}</dd>
    <dt>Gaps</dt><dd>${esc(arr(a1.evidence_gaps).join("; ") || "none")}</dd>
    ${arr(a1.untrusted_content_flags).length ? `<dt>Flags</dt><dd>${esc(arr(a1.untrusted_content_flags).join("; "))}</dd>` : ""}</dl>
    <p><b>Past incidents and procedures</b></p><ul>${refs || "<li class='muted'>none found</li>"}</ul>
    <p><b>Logs used</b></p><ul>${logs || "<li class='muted'>none</li>"}</ul>`;
}
function renderDiagnosis(a2, rep) {
  // The merged diagnostic_reporter records one output; the ranked hypotheses and safe checks
  // are persisted in the saved report (rep.report). Prefer the report, fall back to the output.
  const dx = (rep && rep.report) || a2;
  if (!dx) return `<p class="muted">Waiting for the Diagnostic Reporter...</p>`;
  const hyps = arr(dx.hypotheses).filter((h) => h && typeof h === "object").map((h) => `<div class="hyp"><div class="hyp-head"><span>${esc(h.rank)}. ${esc(h.cause)}</span><span class="tag">${esc(h.evidence_strength)}</span></div>
      <div class="bar"><span style="width:${STRENGTH[h.evidence_strength] || 10}%"></span></div>
      <div class="small">${esc(h.reasoning || "")}</div><div class="cites">supports: ${esc(arr(h.supporting).join(", "))}${arr(h.contradicting).length ? ` · contradicts: ${esc(arr(h.contradicting).join(", "))}` : ""}</div></div>`).join("");
  const checks = arr(dx.safe_checks).filter((c) => c && typeof c === "object").map((c) => `<li>${esc(c.check)} <span class="muted">(${esc(c.source)})</span></li>`).join("");
  const conf = (rep && rep.overall_confidence) || dx.overall_confidence || "-";
  return `${hyps || "<p class='muted'>No hypotheses: evidence was insufficient to diagnose.</p>"}
    <dl class="kv"><dt>Confidence</dt><dd>${esc(conf)}</dd>
    <dt>Uncertainties</dt><dd>${esc(arr(dx.uncertainties).join("; ") || "none")}</dd></dl>
    <p><b>Safe checks (inspection only)</b></p><ul>${checks || "<li class='muted'>none</li>"}</ul>`;
}
function renderTools(ts) {
  const calls = ts.filter((t) => t.kind === "tool_call");
  return calls.length ? `<ul class="tool-list">${calls.map((t) => `<li><span class="muted">${hhmmss(t.created_at)}</span><span class="mono">${esc(t.tool)}</span>
    <span class="${t.ok ? "ok" : "notok"}">${esc(t.summary || (t.ok ? "ok" : "failed"))}</span></li>`).join("")}</ul>` : `<p class="muted">No tool calls yet.</p>`;
}
const FAULT_WORDS = { bearing_wear: ["bearing"], cavitation: ["cavitation"], seal_leak: ["seal"],
                      motor_overload: ["overload", "overcurrent", "motor"], misalignment: ["misalign", "alignment"] };
function categoryOf(text) {
  const t = String(text || "").toLowerCase();
  if (FAULT_WORDS[t]) return t;
  return Object.keys(FAULT_WORDS).find((k) => FAULT_WORDS[k].some((w) => t.includes(w))) || null;
}
function topHypothesis(a2, rep) {
  const h = a2 && arr(a2.hypotheses).find((x) => x && typeof x === "object");
  const rh = rep && rep.report && arr(rep.report.hypotheses).find((x) => x && typeof x === "object");
  const best = h || rh;
  if (!best) return null;
  return { text: best.cause || best.fault_category, category: best.fault_category || categoryOf(best.cause) };
}
function reveal(reading, top) {
  const gt = reading && reading.ground_truth;
  if (!gt) return "";
  if (gt.phase !== "fault") {
    return `<div class="reveal miss"><span>Actual state: <b>no fault was active</b> at this reading (${esc(pretty(gt.phase))})</span>
      <span>Agent's top hypothesis: <b>${esc(top ? top.text : "none")}</b></span><span>a false alarm: what did the evidence show?</span></div>`;
  }
  const match = top && top.category === gt.fault;
  return `<div class="reveal ${top ? (match ? "match" : "miss") : ""}"><span>Actual fault: <b>${esc(pretty(gt.fault))}</b>${gt.injected ? ` <span class="tag">injected</span>` : ""}</span>
    <span>Agent's top hypothesis: <b>${esc(top ? top.text : "none")}</b></span>
    <span>${top ? (match ? "&#10003; correct" : "&#10007; different: compare the evidence") : ""}</span></div>`;
}
function renderTimeline() {
  const el = $("#timeline"); if (!el) return;
  const execs = [...state.execs.values()].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  if (!execs.length) return;
  el.innerHTML = execs.map((x) => {
    const r = state.byEvent.get(x.event_id) || {};
    const ts = tracesFor(x.event_id); const rep = state.reports.get(x.event_id);
    const a1 = outputOf(ts, "evidence_gatherer"), a2 = outputOf(ts, "diagnostic_reporter");
    const top = topHypothesis(a2, rep);
    const stages = stagesFor(x, ts, rep).map(([name, s]) => `<div class="stage ${s}"><div class="dot">${s === "done" ? "&#10003;" : s === "fail" ? "!" : ""}</div>${name}</div>`).join("");
    const email = rep ? `<p class="small">Email to <span class="mono">${esc(rep.email_to)}</span>: <span class="tag ${rep.email_status === "submitted" ? "ok" : rep.email_status === "failed" ? "bad" : ""}">${esc(pretty(rep.email_status))}</span> ${esc(rep.email_detail || "")}<br><span class="muted">${esc(rep.email_subject)}</span></p>` : "";
    const statusLine = x.error ? `<span class="tag bad">${esc(x.error)}</span>` : `<span class="tag">${esc(pretty(x.status))}</span>`;
    return `<article class="acard">
      <div class="acard-head"><div><b>Anomaly at ${hhmmss(r.ts || x.created_at)}</b> <span class="muted">reading #${r.seq ?? "?"}</span></div>
        <div class="small">score <b>${num(r.anomaly_score)}</b> · model: <b>${esc(pretty(r.predicted_fault))}</b> · ${statusLine}</div></div>
      <div class="stages">${stages}</div>
      ${reveal(r, top)}
      ${detailsBlock(x.event_id, "ev", "Agent 1 · Evidence", renderEvidence(a1), a1 ? a1.evidence_status || "" : "")}
      ${detailsBlock(x.event_id, "dx", "Agent 2 · Diagnosis & report", renderDiagnosis(a2, rep) + (rep ? email + `<div class="report-md">${md(rep.report_markdown)}</div>` : `<p class="muted">Waiting for the report...</p>`), top ? top.text : (rep ? pretty(rep.email_status) : ""))}
      ${detailsBlock(x.event_id, "tc", "Tool calls", renderTools(ts), `${ts.filter((t) => t.kind === "tool_call").length}`)}
      ${detailsBlock(x.event_id, "raw", "Webhook payload and recipe result", `<p class="small">request_id <span class="mono">${esc(x.request_id || "-")}</span> · Karini status ${esc(x.karini_status || "-")} · polls ${x.poll_count}</p>
        <p><b>Payload sent</b></p><pre class="json">${esc(JSON.stringify(x.payload, null, 2))}</pre>
        <p><b>Final answer</b></p><pre class="json">${esc(x.final_answer ? JSON.stringify(x.final_answer, null, 2) : "-")}</pre>`)}
    </article>`;
  }).join("");
}

// ----------------------------------------------------------------------------- tiny markdown renderer (escaped first)
function inline(s) { return s.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>"); }
function md(src) {
  const lines = esc(src || "").split("\n"); let out = "", i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (/^\|.*\|$/.test(l.trim())) {
      const rows = []; while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) rows.push(lines[i++].trim());
      const cells = (r) => r.slice(1, -1).split("|").map((c) => c.trim());
      out += "<table>" + rows.filter((r) => !/^\|[\s:|-]+\|$/.test(r)).map((r, k) => `<tr>${cells(r).map((c) => (k === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`)).join("")}</tr>`).join("") + "</table>";
      continue;
    }
    if (/^### /.test(l)) out += `<h3>${inline(l.slice(4))}</h3>`;
    else if (/^## /.test(l)) out += `<h2>${inline(l.slice(3))}</h2>`;
    else if (/^# /.test(l)) out += `<h1>${inline(l.slice(2))}</h1>`;
    else if (/^&gt; /.test(l)) out += `<blockquote>${inline(l.slice(5))}</blockquote>`;
    else if (/^- /.test(l)) { let items = ""; while (i < lines.length && /^- /.test(lines[i])) items += `<li>${inline(lines[i++].slice(2))}</li>`; out += `<ul>${items}</ul>`; continue; }
    else if (l.trim()) out += `<p>${inline(l)}</p>`;
    i++;
  }
  return out;
}

// ----------------------------------------------------------------------------- boot
(async function boot() {
  try { state.cfg = await api("/api/config"); } catch { state.cfg = null; }
  route();
})();
