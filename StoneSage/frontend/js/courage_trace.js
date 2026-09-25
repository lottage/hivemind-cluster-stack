/**
 * 🧭 Courage trace (Engine Studio → Engine Console → 🧭 COURAGE TRACE).
 * One row per Courage turn from backend courage/trace.py: how it was handled, how it ended, how long it took,
 * and the escalation triggers it would have fired (recorded only; nothing acts on them yet). Click a row for its
 * steps: each model call (ms, tokens, tool calls asked for) and each tool call (args, ok/error, ms).
 * Backend: GET /api/courage/trace?limit=, GET /api/courage/trace/summary?hours=
 */

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const S = { turns: [], summary: null, open: new Set(), onlyFlagged: false, hours: 24, timer: null, bound: false };

const OUTCOME = {
  answered: ['✓', 'var(--term-success, #22c55e)'],
  asked_approval: ['?', 'var(--term-accent-gold, #eab308)'],
  step_cap: ['⟳', 'var(--term-error, #ef4444)'],
  llm_error: ['✗', 'var(--term-error, #ef4444)'],
  error: ['✗', 'var(--term-error, #ef4444)'],
  abandoned: ['…', 'var(--term-text-muted)'],
};
const TRIGGER_HELP = {
  tool_error: 'a tool returned an error',
  invalid_args: 'a tool call was refused before running (bad or unsafe arguments)',
  repeated_call: 'the same tool with the same arguments twice in one turn',
  nudged: 'the model described a tool call instead of making it',
  step_cap: 'ran out of steps without answering',
  llm_error: 'the coordinator on :8001 did not answer',
  empty_answer: 'the model ended with no text',
};

const secs = (ms) => (ms == null ? '–' : ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);
const when = (at) => new Date(at * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' });
const chip = (text, color, title = '') =>
  `<span title="${esc(title)}" style="display:inline-block;padding:0 5px;margin:1px 2px;border:1px solid ${color};color:${color};border-radius:3px;font-size:0.68rem;">${esc(text)}</span>`;

function renderSummary() {
  const s = S.summary;
  if (!s) return '<div style="color:var(--term-text-muted)">Loading…</div>';
  if (!s.turns) return `<div style="color:var(--term-text-muted)">No Courage turns in the last ${s.hours} h yet.</div>`;
  const counts = (obj, colorFn, help = {}) => Object.entries(obj || {}).sort((a, b) => b[1] - a[1])
    .map(([k, n]) => chip(`${k} ${n}`, colorFn(k), help[k] || '')).join('') || '<small>none</small>';
  return `
    <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:8px; font-size:0.74rem;">
      <div><b>${s.turns}</b> turns · last ${s.hours} h<br><small>p50 ${secs(s.ms_p50)} · p95 ${secs(s.ms_p95)}</small></div>
      <div>Outcomes<br>${counts(s.outcomes, (k) => (OUTCOME[k] || [0, 'var(--term-text-muted)'])[1])}</div>
      <div>Handled by<br>${counts(s.paths, () => 'var(--term-text-muted)')}</div>
      <div>Triggers (recorded only)<br>${counts(s.triggers, () => 'var(--term-error, #ef4444)', TRIGGER_HELP)}</div>
      <div>Tool errors<br>${counts(s.tool_errors, () => 'var(--term-error, #ef4444)')}</div>
    </div>`;
}

function renderSteps(t) {
  const rows = (t.steps || []).map((s) => {
    if ('llm' in s) {
      return `<div>🧠 model ${secs(s.llm)} · ${s.tokens} tokens · ${s.calls ? `asked for ${s.calls} tool call${s.calls > 1 ? 's' : ''}` : 'answered'}</div>`;
    }
    const mark = s.ok ? '<span style="color:var(--term-success,#22c55e)">ok</span>'
      : `<span style="color:var(--term-error,#ef4444)">${s.refused ? 'refused' : 'error'}: ${esc(s.error)}</span>`;
    return `<div>🔧 <b>${esc(s.tool)}</b> <code style="font-size:0.66rem">${esc(s.args)}</code> · ${mark}${s.ms != null ? ` · ${secs(s.ms)}` : ''}</div>`;
  }).join('');
  return `<div style="margin:4px 0 6px 18px; font-size:0.7rem; line-height:1.5;">
      ${rows || '<div style="color:var(--term-text-muted)">no model or tool calls</div>'}
      <div style="margin-top:3px; color:var(--term-text-muted)">Answer: ${esc(t.final) || '–'}</div>
      <div style="color:var(--term-text-muted)">Model total ${secs(t.llm?.ms)} over ${t.llm?.calls ?? 0} call(s), ${t.llm?.tokens ?? 0} tokens · session ${esc(t.session)}</div>
    </div>`;
}

function renderTurns() {
  const turns = S.onlyFlagged ? S.turns.filter((t) => (t.triggers || []).length) : S.turns;
  if (!turns.length) return `<div style="color:var(--term-text-muted); padding:6px 0;">${S.onlyFlagged ? 'No turns with triggers.' : 'No turns recorded yet.'}</div>`;
  return turns.map((t) => {
    const key = `${t.at}|${t.session}`;
    const [icon, color] = OUTCOME[t.outcome] || ['?', 'var(--term-text-muted)'];
    const trig = (t.triggers || []).map((x) => chip(x, 'var(--term-error, #ef4444)', TRIGGER_HELP[x] || '')).join('');
    const open = S.open.has(key);
    return `<div style="border-bottom:1px solid var(--term-border-dim); padding:3px 0;">
        <div data-turn="${esc(key)}" style="cursor:pointer; display:flex; gap:8px; align-items:baseline; font-size:0.74rem;">
          <span style="color:${color}; font-weight:bold; width:1em;" title="${esc(t.outcome)}">${icon}</span>
          <span style="color:var(--term-text-muted); min-width:120px;">${when(t.at)}</span>
          <span style="min-width:62px;">${secs(t.ms)}</span>
          <span style="color:var(--term-text-muted); min-width:70px;">${esc(t.path)}</span>
          <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${open ? '▾' : '▸'} ${esc(t.user)}</span>
          <span>${trig}</span>
        </div>
        ${open ? renderSteps(t) : ''}
      </div>`;
  }).join('');
}

function render() {
  const root = $('#courage-trace-root');
  if (!root) return;
  root.innerHTML = `
    <div class="harness-card-title" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
      <span>🧭 COURAGE TRACE — every turn: path, outcome, model and tool calls, escalation triggers</span>
      <span style="display:flex; gap:8px; align-items:center; font-size:0.72rem;">
        <label><input type="checkbox" id="ctrace-flagged" ${S.onlyFlagged ? 'checked' : ''}> only turns with triggers</label>
        <select class="form-input" id="ctrace-hours" style="font-size:0.72rem; padding:1px 4px;">
          ${[1, 24, 168].map((h) => `<option value="${h}" ${S.hours === h ? 'selected' : ''}>${h === 168 ? '7 days' : `${h} h`}</option>`).join('')}
        </select>
        <button type="button" class="term-cmd-btn" id="ctrace-refresh" style="font-size:0.72rem;">[🔄 REFRESH]</button>
      </span>
    </div>
    <div style="margin-bottom:10px;">${renderSummary()}</div>
    <div>${renderTurns()}</div>`;
}

async function refresh() {
  try {
    const [t, s] = await Promise.all([
      fetch('/api/courage/trace?limit=100').then((r) => r.json()),
      fetch(`/api/courage/trace/summary?hours=${S.hours}`).then((r) => r.json()),
    ]);
    S.turns = t.ok ? t.turns : [];
    S.summary = s.ok ? s.summary : null;
  } catch (e) {
    S.summary = { turns: 0, hours: S.hours };
  }
  render();
}

function bind() {
  if (S.bound) return;
  const root = $('#courage-trace-root');
  if (!root) return;
  S.bound = true;
  root.addEventListener('click', (e) => {
    const row = e.target.closest('[data-turn]');
    if (row) {
      const k = row.dataset.turn;
      if (S.open.has(k)) S.open.delete(k); else S.open.add(k);
      render();
      return;
    }
    if (e.target.id === 'ctrace-refresh') refresh();
  });
  root.addEventListener('change', (e) => {
    if (e.target.id === 'ctrace-flagged') { S.onlyFlagged = e.target.checked; render(); }
    if (e.target.id === 'ctrace-hours') { S.hours = +e.target.value; refresh(); }
  });
}

export async function openCourageTrace() {
  bind();
  await refresh();
  if (S.timer) clearInterval(S.timer);
  S.timer = setInterval(() => { if ($('#econsole-layer-trace')?.style.display !== 'none') refresh(); }, 15000);
}

window.openCourageTrace = openCourageTrace;
