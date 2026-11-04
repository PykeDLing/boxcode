"use strict";

// 页面上的数据大多来自仓库和模型（任务、工具参数、模型的回复、报错），可能藏着注入的 HTML。
// 一律当文本放进页面（textContent / 文本节点），不拼 innerHTML。

const MODE_LABELS = { "read-only": "只读", "workspace-write": "工作区可写", "full-auto": "全自动" };
const MODE_HINTS = {
  "read-only": "只能读工作区。写文件一律拒绝；执行命令每次都问，放行了也在只读沙盒里跑。",
  "workspace-write": "能读写工作区（.git 除外）。联网、git push、装依赖、递归删除、提权这类命令先问你。",
  "full-auto": "所有调用直接放行，不再问你；命令仍然在沙盒里执行。",
};
const STATUS = {
  running: { label: "运行中", tone: "accent", icon: "●" },
  done: { label: "完成", tone: "good", icon: "✓" },
  verify_failed: { label: "自检未通过", tone: "critical", icon: "✕" },
  max_turns: { label: "超出轮数", tone: "warning", icon: "!" },
  refused: { label: "模型拒绝", tone: "warning", icon: "!" },
  error: { label: "出错", tone: "critical", icon: "✕" },
  cancelled: { label: "已停止", tone: "muted", icon: "■" },
  crashed: { label: "崩溃", tone: "critical", icon: "✕" },
  unfinished: { label: "未结束", tone: "muted", icon: "○" },
};
const CATEGORY = { bugfix: "修 bug", feature: "实现功能", injection: "注入" };
const DECISION = {
  allow: { label: "放行", tone: "good" },
  deny: { label: "拒绝", tone: "critical" },
  invalid: { label: "参数无效", tone: "muted" },
};

// ---- 小工具 ----

const $ = (id) => document.getElementById(id);
// 每次调用接口都带上本次窗口的 token：窗口被导航到别的页面时，那个页面拿不到它（见 gui/api.py）
const TOKEN = document.currentScript.dataset.token;
const API = new Proxy({}, { get: (_, name) => (...args) => window.pywebview.api[name](TOKEN, ...args) });
const api = () => API;
// 只认对象自己的键：页面上显示的状态名来自轨迹文件，可能是 "constructor" 这种名字
const lookup = (table, key) => (Object.hasOwn(table, key) ? table[key] : undefined);
// 要确认的命令里，控制字符、零宽字符、双向文字控制符都显示成 ⟨U+XXXX⟩，不能用它们把内容藏起来
const INVISIBLE = /[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]/g;
const revealInvisible = (text) =>
  text.replace(INVISIBLE, (c) => `⟨U+${c.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}⟩`);
// 确认卡片出现后，按钮过这么久才能点：连点“放行”不会把紧跟着的下一条命令也放行了
const APPROVAL_ARM_MS = 700;

function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat()) {
    if (c != null && c !== false) el.append(c instanceof Node ? c : String(c));
  }
  return el;
}

const nf = new Intl.NumberFormat("zh-CN");
const pad = (n) => String(n).padStart(2, "0");
const fmtInt = (n) => (n == null ? "—" : nf.format(n));
const fmtPct = (r) => (r == null ? "—" : `${Math.round(r * 100)}%`);

function fmtSec(s) {
  if (s == null) return "—";
  if (s < 1) return `${Math.round(s * 1000)}ms`;
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${Math.floor(s / 60)}m${pad(Math.round(s % 60))}s`;
}

function fmtOffset(s) {
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m${pad(Math.round(s % 60))}s`;
}

function fmtTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function reportTime(id) {
  // 20261104-000413 → 11-04 00:04
  const m = /^\d{4}(\d{2})(\d{2})-(\d{2})(\d{2})/.exec(id);
  return m ? `${m[1]}-${m[2]} ${m[3]}:${m[4]}` : id;
}

function badge(key) {
  const s = lookup(STATUS, key) || STATUS.unfinished;
  return h("span", { class: `badge tone-${s.tone}` }, h("span", { class: "badge-icon", "aria-hidden": "true", text: s.icon }), s.label);
}

const chip = (label, tone = "muted") => h("span", { class: `chip tone-${tone}`, text: label });
// 模型的总结常带 `代码`：拆成文本节点和 <code>，仍然不拼 HTML
function richText(text) {
  return String(text).split(/`([^`\n]+)`/).map((part, i) => (i % 2 ? h("code", { text: part }) : part));
}

const pre = (text, kind = "") => h("pre", { class: `pre ${kind}`, text: text == null ? "" : String(text) });

function tile(label, value, sub) {
  return h("div", { class: "tile" },
    h("div", { class: "tile-label", text: label }),
    h("div", { class: "tile-value", text: value }),
    sub ? h("div", { class: "tile-sub", text: sub }) : null);
}

let toastTimer = null;
function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4200);
}

function showError(err) {
  toast(`出错了：${err && err.message ? err.message : err}`);
}

function parseArgs(raw) {
  try {
    const v = JSON.parse(raw || "{}");
    return v && typeof v === "object" ? v : null;
  } catch {
    return null;
  }
}

// ---- 一次运行：头部、指标、总结、时间线。新任务、历史轨迹、评测三处共用 ----

function summarize(events) {
  const llm = events.filter((e) => e.event === "llm_call");
  const tools = events.filter((e) => e.event === "tool_call");
  const sum = (arr, k) => arr.reduce((a, e) => a + (e[k] || 0), 0);
  return {
    llmCalls: llm.length,
    prompt: sum(llm, "prompt_tokens"),
    completion: sum(llm, "completion_tokens"),
    cached: sum(llm, "cached_tokens"),
    toolCalls: tools.length,
    denied: tools.filter((e) => e.decision === "deny").length,
    failed: tools.filter((e) => !e.ok && e.decision === "allow").length,
    seconds: events.length > 1 ? events[events.length - 1].ts - events[0].ts : 0,
  };
}

function toolTarget(tool, args) {
  if (!args) return "";
  if (tool === "run_command") return `$ ${args.command || ""}`;
  if (tool === "grep") return `/${args.pattern || ""}/${args.path ? `  ${args.path}` : ""}`;
  if (tool === "list_dir") return args.path || ".";
  return args.path || "";
}

function toolDetail(tool, args, raw) {
  if (!args) return [pre(raw)];
  if (tool === "edit_file") {
    return [
      h("div", { class: "kv" }, "文件 ", h("span", { class: "mono", text: args.path })),
      h("div", { class: "diff-label", text: "原文" }), pre(args.old_string, "old"),
      h("div", { class: "diff-label", text: "改为" }), pre(args.new_string, "new"),
    ];
  }
  if (tool === "write_file") {
    return [h("div", { class: "kv" }, "文件 ", h("span", { class: "mono", text: args.path })), pre(args.content, "new")];
  }
  if (tool === "run_command") return [pre(args.command)];
  return [pre(JSON.stringify(args, null, 2))];
}

function timelineItem(e, t0) {
  let dot = "";
  let title = [];
  const meta = [];
  let detail = null;

  switch (e.event) {
    case "run_start":
      title = [h("strong", { text: "开始运行" })];
      meta.push([e.model, lookup(MODE_LABELS, e.mode) || e.mode, `沙盒 ${e.sandbox === "seatbelt" ? "Seatbelt" : "未启用"}`,
        `网络${e.allow_network ? "开" : "关"}`].join(" · "));
      break;
    case "llm_call": {
      dot = "accent";
      const calls = e.tool_calls || [];
      title = [h("strong", { text: `模型调用 · 第 ${e.turn} 轮` })];
      if (calls.length) title.push(h("span", { class: "tl-meta", text: "→" }), ...calls.map((n) => h("code", { class: "chip", text: n })));
      if (e.stop_reason === "refusal") title.push(chip("拒绝回答", "warning"));
      meta.push(`${fmtSec(e.latency_s)} · 输入 ${fmtInt(e.prompt_tokens)}（缓存 ${fmtInt(e.cached_tokens)}）· 输出 ${fmtInt(e.completion_tokens)}`);
      if (!calls.length) meta.push("没有调用工具，认为做完了");
      break;
    }
    case "tool_call": {
      dot = "ink";
      const args = parseArgs(e.arguments);
      const d = lookup(DECISION, e.decision) || DECISION.invalid;
      title = [
        h("code", { class: "tool-name", text: e.tool }),
        h("span", { class: "tool-target mono", text: toolTarget(e.tool, args), title: toolTarget(e.tool, args) }),
        chip(d.label, d.tone),
        e.decision === "allow" && !e.ok ? chip("出错", "critical") : null,
      ];
      meta.push([e.reason, fmtSec(e.duration_s), e.output_chars != null ? `结果 ${fmtInt(e.output_chars)} 字符` : null]
        .filter(Boolean).join(" · "));
      if (e.exception) meta.push(`异常：${e.exception}`);
      detail = h("details", null, h("summary", { text: "参数" }), h("div", { class: "tl-detail" }, toolDetail(e.tool, args, e.arguments)));
      break;
    }
    case "verify":
      dot = e.passed ? "good" : "critical";
      title = [h("strong", { text: e.passed ? "自检通过" : "自检未通过" }), h("span", { class: "tool-target mono", text: e.command })];
      meta.push(`退出码 ${e.exit_code}`);
      break;
    case "llm_error":
      dot = "critical";
      title = [h("strong", { text: "模型接口出错" })];
      meta.push(e.error || "");
      break;
    case "run_end": {
      const s = lookup(STATUS, e.status) || STATUS.unfinished;
      dot = s.tone === "accent" || s.tone === "muted" ? "" : s.tone;
      title = [h("strong", { text: "结束" }), badge(e.status)];
      meta.push(`调用模型 ${e.turns ?? "—"} 次 · 修正 ${e.fix_rounds ?? 0} 轮`);
      break;
    }
    default:
      title = [h("strong", { text: e.event })];
  }

  return h("li", { class: "tl" },
    h("div", { class: "tl-time", text: `+${fmtOffset(Math.max(0, (e.ts || t0) - t0))}` }),
    h("div", { class: `tl-dot ${dot}` }),
    h("div", { class: "tl-body" },
      h("div", { class: "tl-title" }, title),
      meta.map((m) => h("div", { class: "tl-meta", text: m })),
      detail));
}

class RunView {
  constructor(scroller) {
    this.scroller = scroller; // 外层滚动容器：运行中自动滚到底
    this.head = h("div", { class: "run-head" });
    this.tiles = h("div", { class: "tiles" });
    this.approvals = h("div", { class: "approvals" });
    this.final = h("div", { class: "final", hidden: true });
    this.timeline = h("ol", { class: "timeline" });
    this.el = h("div", { class: "run-view" },
      this.approvals, this.head, this.tiles, this.final,
      h("h3", { class: "section-title", text: "执行过程" }), this.timeline);
    this.events = [];
    this.live = false;
    this.pendingTask = "";
  }

  load(events, { live = false, task = "" } = {}) {
    this.events = [];
    this.live = live;
    this.pendingTask = task;
    this.timeline.replaceChildren();
    this.approvals.replaceChildren();
    for (const e of events) this.add(e, false);
    this.refresh();
  }

  add(e, refresh = true) {
    const nearBottom = this.scroller.scrollHeight - this.scroller.scrollTop - this.scroller.clientHeight < 120;
    this.events.push(e);
    this.timeline.append(timelineItem(e, this.events[0].ts));
    if (e.event === "run_end") this.live = false;
    if (refresh) {
      this.refresh();
      if (this.live && nearBottom) this.scroller.scrollTop = this.scroller.scrollHeight;
    }
  }

  stopLive() {
    this.live = false;
    this.refresh();
  }

  refresh() {
    const start = this.events.find((e) => e.event === "run_start");
    const end = [...this.events].reverse().find((e) => e.event === "run_end");
    const status = end ? end.status : this.live ? "running" : "unfinished";

    const meta = [];
    if (start) {
      meta.push(h("span", { text: start.model }), h("span", { text: lookup(MODE_LABELS, start.mode) || start.mode }));
      meta.push(h("span", { text: `沙盒 ${start.sandbox === "seatbelt" ? "Seatbelt" : "未启用"} · 网络${start.allow_network ? "开" : "关"}` }));
      meta.push(h("span", { class: "mono", text: start.workspace, title: start.workspace }));
      meta.push(h("span", { text: fmtTime(start.ts) }));
    }
    this.head.replaceChildren(
      h("div", { class: "run-head-top" }, badge(status), start ? h("span", { class: "mono tl-meta", text: start.run_id }) : null),
      h("div", { class: "run-task", text: start ? start.task : this.pendingTask }),
      h("div", { class: "run-meta" }, meta));

    const s = summarize(this.events);
    this.tiles.replaceChildren(
      tile("模型调用", fmtInt(s.llmCalls)),
      tile("工具调用", fmtInt(s.toolCalls), `拒绝 ${s.denied} · 出错 ${s.failed}`),
      tile("输入 token", fmtInt(s.prompt), s.prompt ? `命中缓存 ${fmtPct(s.cached / s.prompt)}` : null),
      tile("输出 token", fmtInt(s.completion)),
      tile("耗时", fmtSec(s.seconds)));

    const text = end ? end.final_message || end.error : null;
    this.final.hidden = !text;
    if (text) {
      const isError = !end.final_message;
      this.final.className = `final${isError ? " is-error" : ""}`;
      this.final.replaceChildren(
        h("div", { class: "final-title", text: isError ? "错误" : "Agent 的总结" }),
        h("div", { class: "final-body" }, richText(text)));
    }
  }
}

// ---- 全局状态 ----

const state = {
  view: "run",
  mode: "workspace-write",
  running: false,
  stopping: false,
  approvals: new Map(), // id → 卡片
  runs: [],
  runsLoaded: false,
  selectedRun: null,
  tasks: [],
  selectedTasks: new Set(),
  reports: [],
  evalLoaded: false,
  evalRunning: false,
  evalLive: null, // { reportId, order: [id], progress: Map(id → { state, result }) }
  selectedReport: null,
  reportData: null,
  selectedEvalTask: null,
};

let liveView = null;
let historyView = null;
let evalTraceView = null;

// Python 往页面推消息都走这里（app.py 里的 push）
const handlers = {
  trace(msg) {
    if (!liveView.live) return;
    liveView.add(msg.event);
  },
  approval(msg) {
    const card = approvalCard(msg);
    state.approvals.set(msg.id, card);
    liveView.approvals.append(card);
    updateNav();
  },
  approval_resolved(msg) {
    const card = state.approvals.get(msg.id);
    if (card) card.remove();
    state.approvals.delete(msg.id);
    updateNav();
  },
  run_finished(msg) {
    state.running = false;
    state.stopping = false;
    state.runsLoaded = false; // 历史列表里多了一条
    liveView.stopLive();
    // “开始”和“停止”在同一个位置：刚停下来时多点的那一下不能把任务又开起来
    $("f-start").disabled = true;
    setTimeout(() => { $("f-start").disabled = false; }, 1000);
    updateRunControls();
    updateNav();
    if (state.view !== "run") {
      const s = lookup(STATUS, msg.status) || STATUS.unfinished;
      toast(`任务结束：${s.label}`);
    }
  },
  eval_progress(msg) {
    const live = state.evalLive;
    if (!live || live.reportId !== msg.report_id) return;
    live.progress.set(msg.task_id, { state: msg.state, result: msg.result || null });
    if (state.selectedReport === live.reportId) renderReport();
  },
  async eval_finished(msg) {
    state.evalRunning = false;
    // 先清掉再 await：等待期间新开的一轮评测不能被这里清掉
    if (state.evalLive && state.evalLive.reportId === msg.report_id) state.evalLive = null;
    updateEvalControls();
    updateNav();
    if (msg.error) toast(`评测出错：${msg.error}`);
    else if (state.view !== "eval") toast(msg.stopped ? "评测已停止" : "评测结束");
    await loadReports();
    if (state.selectedReport === msg.report_id) await selectReport(msg.report_id, { keepTask: true });
  },
};

window.boxcode = {
  receive(msg) {
    const fn = handlers[msg && msg.kind];
    if (!fn) return;
    Promise.resolve().then(() => fn(msg)).catch((err) => console.error(err));
  },
};

// ---- 导航 ----

function showView(view) {
  state.view = view;
  for (const btn of document.querySelectorAll(".nav-item")) btn.classList.toggle("active", btn.dataset.view === view);
  for (const id of ["run", "history", "eval"]) $(`view-${id}`).hidden = id !== view;
  if (view === "history" && !state.runsLoaded) loadHistory().catch(showError);
  if (view === "eval" && !state.evalLoaded) loadEval().catch(showError);
  updateNav();
}

function setFlag(navId, cls, text) {
  const flag = $(navId).querySelector(".nav-flag");
  flag.hidden = !cls;
  flag.className = `nav-flag${cls ? ` ${cls}` : ""}`;
  flag.textContent = text || "";
}

function updateNav() {
  const pending = state.approvals.size;
  if (pending && state.view !== "run") setFlag("nav-run", "attention", `${pending} 待确认`);
  else setFlag("nav-run", state.running ? "busy" : null);
  setFlag("nav-eval", state.evalRunning ? "busy" : null);
}

// ---- 新任务 ----

function setMode(mode) {
  state.mode = mode;
  for (const btn of $("f-mode").querySelectorAll("button")) btn.setAttribute("aria-checked", String(btn.dataset.mode === mode));
  $("f-mode-hint").textContent = MODE_HINTS[mode];
}

function updateRunControls() {
  $("run-fields").disabled = state.running;
  $("f-start").hidden = state.running;
  $("f-stop").hidden = !state.running;
  $("f-stop").disabled = state.stopping;
  $("f-stop").textContent = state.stopping ? "正在停止…" : "停止";
}

function showRunError(message) {
  $("f-error").textContent = message;
  $("f-error").hidden = !message;
}

async function startRun(event) {
  event.preventDefault();
  if (state.running) return;
  const request = {
    task: $("f-task").value,
    workspace: $("f-workspace").value.trim(),
    mode: state.mode,
    verify: $("f-verify").value.trim() || null,
    allow_network: $("f-network").checked,
  };
  if (!request.task.trim()) return showRunError("先写要 Agent 做的事");
  if (!request.workspace) return showRunError("先选工作区");
  showRunError("");

  // 先切到运行中再调接口：后台线程可能比这次调用的返回值更早把第一条轨迹推过来
  state.running = true;
  $("run-empty").hidden = true;
  liveView.el.hidden = false;
  liveView.load([], { live: true, task: request.task });
  for (const card of state.approvals.values()) card.remove();
  state.approvals.clear();
  updateRunControls();
  updateNav();

  let res;
  try {
    res = await api().start_run(request);
  } catch (err) {
    res = { ok: false, error: String(err && err.message ? err.message : err) };
  }
  if (!res.ok) {
    state.running = false;
    liveView.live = false;
    liveView.el.hidden = true;
    $("run-empty").hidden = false;
    updateRunControls();
    updateNav();
    showRunError(res.error);
  }
}

async function stopRun() {
  state.stopping = true;
  updateRunControls();
  await api().stop_run();
}

function approvalCard(msg) {
  const params = msg.params || {};
  const body = String(msg.tool === "run_command" ? params.command : JSON.stringify(params, null, 2));
  const lines = body.split("\n").length;
  const answer = (event, approved) => {
    if (event.detail > 1) return; // 双击、三击：不是看过之后点的
    card.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    api().answer_approval(msg.id, approved).catch(showError);
  };
  const buttons = [
    h("button", { type: "button", class: "btn primary small", text: "放行这一次", disabled: true, onclick: (e) => answer(e, true) }),
    h("button", { type: "button", class: "btn small", text: "拒绝", disabled: true, onclick: (e) => answer(e, false) }),
  ];
  const card = h("div", { class: "approval", role: "alertdialog", "aria-label": `需要确认：${msg.reason}`, tabindex: "-1" },
    h("div", { class: "approval-head" },
      h("span", { class: "badge tone-warning" }, h("span", { class: "badge-icon", "aria-hidden": "true", text: "!" }), "需要确认"),
      h("span", { class: "approval-reason", text: msg.reason }),
      h("code", { class: "tool-name", text: msg.tool })),
    pre(revealInvisible(body)),
    h("div", { class: "approval-meta", text: `${lines} 行，${body.length} 个字符` }),
    h("div", { class: "actions" }, ...buttons));
  setTimeout(() => buttons.forEach((b) => { b.disabled = false; }), APPROVAL_ARM_MS);
  setTimeout(() => card.focus(), 0);
  return card;
}

// ---- 历史轨迹 ----

async function loadHistory() {
  state.runs = await api().list_runs();
  state.runsLoaded = true;
  renderRunList();
  if (state.runs.length && !state.runs.some((r) => r.run_id === state.selectedRun)) {
    await selectRun(state.runs[0].run_id);
  } else if (!state.runs.length) {
    $("h-pane").replaceChildren(h("div", { class: "empty" },
      h("div", { class: "empty-title", text: "还没有运行记录" }),
      h("p", { text: "在“新任务”或命令行里跑一次，执行轨迹就会出现在这里。" })));
  }
}

function renderRunList() {
  const q = $("h-filter").value.trim().toLowerCase();
  const runs = state.runs.filter((r) => !q || `${r.task} ${r.workspace}`.toLowerCase().includes(q));
  if (!runs.length) {
    $("h-list").replaceChildren(h("li", { class: "list-empty", text: state.runs.length ? "没有匹配的运行" : "还没有运行记录" }));
    return;
  }
  $("h-list").replaceChildren(...runs.map((r) => {
    const meta = [r.model, lookup(MODE_LABELS, r.mode) || r.mode, r.summary ? `${r.summary.llm_calls} 次模型调用` : null].filter(Boolean).join(" · ");
    return h("li", null, h("button", {
      type: "button",
      class: `run-item${r.run_id === state.selectedRun ? " selected" : ""}`,
      onclick: () => selectRun(r.run_id).catch(showError),
    },
    h("div", { class: "run-item-top" }, badge(r.status || "unfinished"), h("span", { class: "run-item-time", text: fmtTime(r.ts) })),
    h("div", { class: "run-item-task", text: r.task }),
    h("div", { class: "run-item-meta", text: meta, title: r.workspace })));
  }));
}

async function selectRun(runId) {
  state.selectedRun = runId;
  renderRunList();
  const events = await api().load_run(runId);
  if (state.selectedRun !== runId) return; // 等待期间又点了别的
  historyView.load(events);
  $("h-pane").replaceChildren(historyView.el);
  $("h-pane").scrollTop = 0;
}

// ---- 评测 ----

async function loadEval() {
  const [tasks] = await Promise.all([api().list_tasks(), loadReports()]);
  state.tasks = tasks;
  if (!state.evalLoaded) state.selectedTasks = new Set(tasks.map((t) => t.id));
  state.evalLoaded = true;
  renderTasks();
  if (!state.selectedReport && state.reports.length) await selectReport(state.reports[0].id);
  else if (!state.selectedReport) renderReport();
}

async function loadReports() {
  state.reports = await api().list_reports();
  renderReports();
}

function renderTasks() {
  if (!state.tasks.length) {
    $("e-tasks").replaceChildren(h("li", { class: "list-empty", text: "没有找到题目" }));
  } else {
    $("e-tasks").replaceChildren(...state.tasks.map((t) => {
      const box = h("input", {
        type: "checkbox",
        checked: state.selectedTasks.has(t.id),
        disabled: state.evalRunning,
        onchange: (e) => {
          if (e.target.checked) state.selectedTasks.add(t.id);
          else state.selectedTasks.delete(t.id);
          updateEvalControls();
        },
      });
      return h("li", null, h("label", { class: "task-item" },
        box,
        h("div", { class: "task-item-top" },
          h("span", { class: "mono task-item-id", text: t.id, title: t.id }),
          chip(lookup(CATEGORY, t.category) || t.category, t.category === "injection" ? "warning" : "muted")),
        h("div", { class: "task-item-prompt", text: t.prompt, title: t.prompt })));
    }));
  }
  updateEvalControls();
}

function updateEvalControls() {
  const n = state.selectedTasks.size;
  $("e-start").hidden = state.evalRunning;
  $("e-start").disabled = n === 0;
  $("e-start").textContent = n ? `运行所选（${n} 道）` : "运行所选";
  $("e-stop").hidden = !state.evalRunning;
  $("e-toggle-all").textContent = n === state.tasks.length && n > 0 ? "全不选" : "全选";
  $("e-toggle-all").disabled = state.evalRunning;
  for (const box of $("e-tasks").querySelectorAll("input")) box.disabled = state.evalRunning;
}

function renderReports() {
  if (!state.reports.length) {
    $("e-reports").replaceChildren(h("li", { class: "list-empty", text: "还没有评测报告" }));
    return;
  }
  $("e-reports").replaceChildren(...state.reports.map((r) => h("li", null, h("button", {
    type: "button",
    class: `report-item${r.id === state.selectedReport ? " selected" : ""}`,
    onclick: () => selectReport(r.id).catch(showError),
  },
  h("div", { class: "report-item-top" },
    h("span", { class: "run-item-time", text: reportTime(r.id) }),
    h("span", { class: "report-item-rate", text: `${fmtPct(r.pass_rate)} 通过` })),
  h("div", { class: "run-item-meta", text: `${r.model || "—"} · ${r.tasks} 道题` })))));
}

async function selectReport(reportId, { keepTask = false } = {}) {
  state.selectedReport = reportId;
  if (!keepTask) state.selectedEvalTask = null;
  const live = state.evalLive && state.evalLive.reportId === reportId && state.evalRunning;
  const data = live ? null : await api().load_report(reportId);
  if (state.selectedReport !== reportId) return; // 等待期间又点了别的
  state.reportData = data;
  renderReports();
  renderReport();
  if (state.selectedEvalTask) await showEvalTrace(state.selectedEvalTask);
}

async function startEval() {
  $("e-error").hidden = true;
  const ids = state.tasks.map((t) => t.id).filter((id) => state.selectedTasks.has(id));
  const res = await api().start_eval(ids);
  if (!res.ok) {
    $("e-error").textContent = res.error;
    $("e-error").hidden = false;
    return;
  }
  state.evalRunning = true;
  $("e-stop").disabled = false;
  state.evalLive = {
    reportId: res.report_id,
    order: res.task_ids,
    progress: new Map(res.task_ids.map((id) => [id, { state: "pending", result: null }])),
  };
  state.selectedReport = res.report_id;
  state.selectedEvalTask = null;
  state.reportData = null;
  updateEvalControls();
  updateNav();
  renderReports();
  renderReport();
}

function reportRows() {
  // 正在跑的评测：按选题顺序列出每道题的进度；已经结束的：直接用报告里的结果
  const live = state.evalLive;
  if (live && live.reportId === state.selectedReport && !state.reportData) {
    const tasks = new Map(state.tasks.map((t) => [t.id, t]));
    return live.order.map((id) => {
      const p = live.progress.get(id);
      return { id, category: (p.result && p.result.category) || (tasks.get(id) || {}).category, state: p.state, result: p.result };
    });
  }
  return ((state.reportData && state.reportData.results) || []).map((r) => ({ id: r.id, category: r.category, state: "done", result: r }));
}

function renderReport() {
  const pane = $("e-pane");
  if (!state.selectedReport) {
    pane.replaceChildren(h("div", { class: "empty" },
      h("div", { class: "empty-title", text: "还没有评测报告" }),
      h("p", { text: "在左边选好题目点“运行所选”。每做完一道题，结果就会出现在这里。" })));
    return;
  }
  const rows = reportRows();
  const done = rows.filter((r) => r.result).map((r) => r.result);
  const injection = done.filter((r) => r.category === "injection");
  const n = done.length;
  const running = state.evalRunning && state.evalLive && state.evalLive.reportId === state.selectedReport;
  const model = (state.reportData && state.reportData.model) || (running ? $("model-info").dataset.model : null);

  const head = h("div", { class: "run-head" },
    h("div", { class: "run-head-top" },
      running ? badge("running") : null,
      h("span", { class: "run-task", text: `评测报告 ${reportTime(state.selectedReport)}` })),
    h("div", { class: "run-meta" },
      h("span", { class: "mono", text: state.selectedReport }),
      model ? h("span", { text: model }) : null,
      h("span", { text: running ? `已完成 ${n} / ${rows.length} 道` : `${rows.length} 道题` })));

  const sumTokens = done.reduce((a, r) => a + r.summary.prompt_tokens + r.summary.completion_tokens, 0);
  const tiles = h("div", { class: "tiles" },
    tile("通过率", n ? fmtPct(done.filter((r) => r.passed).length / n) : "—", n ? `${done.filter((r) => r.passed).length} / ${n} 道` : null),
    tile("注入诱导率", injection.length ? fmtPct(injection.filter((r) => r.induced).length / injection.length) : "—",
      injection.length ? `${injection.length} 道注入题` : "没有注入题"),
    tile("平均模型调用", n ? (done.reduce((a, r) => a + r.summary.llm_calls, 0) / n).toFixed(1) : "—"),
    tile("总 token", n ? fmtInt(sumTokens) : "—"));

  const tbody = h("tbody", null, rows.map((row) => {
    const r = row.result;
    let resultCell;
    if (row.state === "running") resultCell = badge("running");
    else if (!r) resultCell = h("span", { class: "status-text", text: "等待" });
    else {
      resultCell = h("span", { class: "cell-badges", title: r.check_detail || null },
        h("span", { class: `badge tone-${r.passed ? "good" : "critical"}` },
          h("span", { class: "badge-icon", "aria-hidden": "true", text: r.passed ? "✓" : "✕" }), r.passed ? "通过" : "未通过"),
        r.category === "injection" ? chip(r.induced ? "被诱导" : "未被诱导", r.induced ? "critical" : "muted") : null);
    }
    const clickable = Boolean(r && r.trace_path);
    return h("tr", {
      class: [clickable ? "clickable" : "", row.id === state.selectedEvalTask ? "selected" : ""].join(" ").trim() || null,
      onclick: clickable ? () => { state.selectedEvalTask = row.id; renderReport(); showEvalTrace(row.id).catch(showError); } : null,
    },
    h("td", { class: "col-id mono", text: row.id, title: row.id }),
    h("td", { text: lookup(CATEGORY, row.category) || row.category || "" }),
    h("td", null, resultCell),
    h("td", { class: "status-text", text: r ? (lookup(STATUS, r.agent_status) || { label: r.agent_status }).label : "" }),
    h("td", { class: "num", text: r ? fmtSec(r.seconds) : "" }),
    h("td", { class: "num", text: r ? fmtInt(r.summary.llm_calls) : "" }),
    h("td", { class: "num", text: r ? fmtInt(r.summary.prompt_tokens + r.summary.completion_tokens) : "" }));
  }));

  const table = h("div", { class: "table-wrap" }, h("table", null,
    h("thead", null, h("tr", null,
      h("th", { class: "col-id", text: "题目" }), h("th", { text: "类型" }), h("th", { text: "结果" }), h("th", { text: "Agent 状态" }),
      h("th", { class: "num", text: "耗时" }), h("th", { class: "num", text: "模型调用" }), h("th", { class: "num", text: "token" }))),
    tbody));

  const traceSection = h("div", { class: "trace-section", id: "e-trace" },
    state.selectedEvalTask ? evalTraceView.el : h("p", { class: "hint", text: "点一道做完的题，查看它的执行轨迹。" }));

  pane.replaceChildren(h("div", { class: "report-view" }, head, tiles, table, traceSection));
}

async function showEvalTrace(taskId) {
  const events = await api().load_eval_trace(state.selectedReport, taskId);
  if (state.selectedEvalTask !== taskId) return;
  evalTraceView.load(events);
  const section = $("e-trace");
  if (section) section.replaceChildren(evalTraceView.el);
}

// ---- 启动 ----

async function init() {
  // 拖进窗口的文件或链接会被直接打开，那个页面不受这里的 CSP 管：一律拦掉
  for (const type of ["dragover", "drop"]) window.addEventListener(type, (e) => e.preventDefault());
  liveView = new RunView($("run-pane"));
  liveView.el.hidden = true;
  $("run-pane").append(liveView.el);
  historyView = new RunView($("h-pane"));
  evalTraceView = new RunView($("e-pane"));

  const info = await api().info();
  $("f-workspace").value = info.cwd;
  const rows = [
    ["模型", info.model],
    ["接口", info.provider],
    info.effort ? ["思考", info.effort] : null,
    ["沙盒", info.sandbox ? "Seatbelt" : "不可用"],
  ].filter(Boolean);
  const dl = $("model-info");
  dl.dataset.model = info.model;
  dl.replaceChildren(...rows.flatMap(([k, v]) => [h("dt", { text: k }), h("dd", { text: v, title: v })]));
  $("history-sub").textContent = `${info.runs_dir} 里每次运行的执行轨迹，每一步一行 JSON。`;

  for (const btn of document.querySelectorAll(".nav-item")) btn.addEventListener("click", () => showView(btn.dataset.view));
  for (const btn of $("f-mode").querySelectorAll("button")) btn.addEventListener("click", () => setMode(btn.dataset.mode));
  setMode(state.mode);

  $("run-form").addEventListener("submit", (e) => startRun(e).catch(showError));
  $("f-task").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("run-form").requestSubmit();
  });
  $("f-pick").addEventListener("click", async () => {
    const path = await api().pick_folder();
    if (path) $("f-workspace").value = path;
  });
  $("f-network").addEventListener("change", (e) => { $("f-network-warn").hidden = !e.target.checked; });
  $("f-stop").addEventListener("click", () => stopRun().catch(showError));

  $("h-refresh").addEventListener("click", () => loadHistory().catch(showError));
  $("h-filter").addEventListener("input", renderRunList);

  $("e-refresh").addEventListener("click", () => loadEval().catch(showError));
  $("e-start").addEventListener("click", () => startEval().catch(showError));
  $("e-stop").addEventListener("click", () => {
    $("e-stop").disabled = true;
    api().stop_eval().catch(showError);
  });
  $("e-toggle-all").addEventListener("click", () => {
    const all = state.selectedTasks.size === state.tasks.length;
    state.selectedTasks = all ? new Set() : new Set(state.tasks.map((t) => t.id));
    renderTasks();
  });

  updateRunControls();
  $("f-task").focus();
}

function whenReady(fn) {
  const ready = () => window.pywebview && window.pywebview.api && typeof window.pywebview.api.info === "function";
  if (ready()) fn();
  else window.addEventListener("pywebviewready", fn, { once: true });
}

whenReady(() => init().catch(showError));
