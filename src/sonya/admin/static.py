"""Static HTML for the admin panel SPA."""

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sonya Admin</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; display: flex; height: 100vh; overflow: hidden; }

/* Sidebar */
.sidebar { width: 240px; background: #161b22; border-right: 1px solid #30363d; display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-header { padding: 20px; border-bottom: 1px solid #30363d; }
.sidebar-header h1 { font-size: 18px; color: #f0f; font-weight: 700; }
.sidebar-header span { font-size: 11px; color: #8b949e; }
.nav { flex: 1; padding: 10px 0; }
.nav-item { display: flex; align-items: center; padding: 10px 20px; cursor: pointer; color: #8b949e; font-size: 14px; transition: all 0.15s; border-left: 3px solid transparent; }
.nav-item:hover { background: #1c2128; color: #c9d1d9; }
.nav-item.active { background: #1c2128; color: #f0f; border-left-color: #f0f; }
.nav-item svg { width: 18px; height: 18px; margin-right: 12px; fill: currentColor; }
.sidebar-footer { padding: 15px 20px; border-top: 1px solid #30363d; font-size: 11px; color: #484f58; }

/* Main */
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.topbar { padding: 15px 25px; border-bottom: 1px solid #30363d; background: #161b22; }
.topbar h2 { font-size: 16px; font-weight: 600; }
.content { flex: 1; overflow-y: auto; padding: 25px; }

/* Cards */
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 15px; }
.card h3 { font-size: 13px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
.card pre { font-size: 12px; color: #7ee787; white-space: pre-wrap; word-break: break-all; }
.stat { display: inline-block; background: #1c2128; border-radius: 6px; padding: 8px 14px; margin: 4px; font-size: 13px; }
.stat b { color: #f0f; }
.provider-grid { display:grid; grid-template-columns:minmax(240px,.75fr) minmax(420px,2fr); gap:15px; align-items:start; }
.provider-stack { display:flex; flex-direction:column; gap:8px; }
.provider-row { background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:10px; }
.provider-row.selected { border-color:#f0f; }
.provider-head, .provider-actions { display:flex; justify-content:space-between; gap:8px; align-items:center; flex-wrap:wrap; }
.provider-actions { justify-content:flex-start; }
.provider-meta { color:#8b949e; font-size:11px; margin-top:4px; overflow-wrap:anywhere; }
.provider-form { display:grid; grid-template-columns:130px minmax(0,1fr); gap:8px; align-items:center; }
.provider-form input, .provider-form select, .provider-filter { background:#0d1117; border:1px solid #30363d; border-radius:4px; padding:7px; color:#c9d1d9; min-width:0; }
.provider-button { background:#30363d; color:#c9d1d9; border:0; padding:6px 10px; border-radius:4px; cursor:pointer; font-size:11px; }
.provider-button.primary { background:#238636; color:white; }
.provider-button.danger { background:#da363322; color:#f85149; }
.provider-badge { display:inline-block; padding:2px 7px; border-radius:10px; font-size:10px; background:#30363d; color:#c9d1d9; }
.provider-badge.active, .provider-badge.free, .provider-badge.available { background:#23863633; color:#7ee787; }
.provider-badge.error, .provider-badge.banned { background:#da363322; color:#f85149; }
.provider-models { max-height:540px; overflow:auto; }
.provider-summary { display:grid; grid-template-columns:repeat(5,minmax(100px,1fr)); gap:8px; margin-bottom:15px; }
.provider-summary .card { margin:0; padding:12px; }
.provider-summary strong { display:block; color:#f0f; font-size:20px; }
details.provider-legacy summary { cursor:pointer; color:#8b949e; }
@media (max-width:1050px) { .provider-grid { grid-template-columns:1fr; } .provider-summary { grid-template-columns:repeat(2,minmax(100px,1fr)); } }

/* Events */
.event { border-left: 3px solid #30363d; padding: 10px 15px; margin: 8px 0; font-size: 13px; }
.event.thought { border-color: #f0f; }
.event.memory { border-color: #7ee787; }
.event.audit { border-color: #ffa657; }
.event.dialog-in { border-color: #58a6ff; }
.event.dialog-out { border-color: #3fb950; }
.event.action { border-color: #d2a8ff; }
.event.error { border-color: #f85149; }
.event.system { border-color: #6e7681; }
.event.task { border-color: #d29922; }
.event .meta { color: #484f58; font-size: 11px; margin-bottom: 4px; }
.event .body { color: #c9d1d9; }
.event .body .text { white-space: pre-wrap; line-height: 1.5; }
.event .body .tool-line { color: #d2a8ff; font-family: monospace; font-size: 12px; }
.event .body .observation-line { color: #8b949e; font-style: italic; font-size: 12px; }
.event .body .raw-toggle { color: #6e7681; font-size: 11px; cursor: pointer; margin-top: 6px; user-select: none; }
.event .body .raw-toggle:hover { color: #c9d1d9; }
.event .body pre.raw { background: #0d1117; padding: 8px; border-radius: 4px; font-size: 11px; max-height: 300px; overflow: auto; margin-top: 6px; display: none; }
.event .body pre.raw.show { display: block; }

/* Filter chips */
.chip { display: inline-block; padding: 4px 10px; border-radius: 12px; background: #21262d; border: 1px solid #30363d; color: #8b949e; font-size: 12px; cursor: pointer; transition: all 0.15s; }
.chip:hover { background: #30363d; color: #c9d1d9; }
.chip.on { background: #f0f; color: #0d1117; border-color: #f0f; }

/* Chat */
.chat-container { display: flex; flex-direction: column; height: 100%; }
.chat-messages { flex: 1; overflow-y: auto; padding: 15px; }
.chat-msg { margin: 10px 0; padding: 12px 16px; border-radius: 12px; max-width: 80%; font-size: 14px; line-height: 1.5; }
.chat-msg.user { background: #1f6feb; color: white; margin-left: auto; border-bottom-right-radius: 4px; }
.chat-msg.sonya { background: #21262d; border: 1px solid #30363d; border-bottom-left-radius: 4px; }
.chat-input { display: flex; padding: 15px; border-top: 1px solid #30363d; background: #161b22; }
.chat-input textarea { flex: 1; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 12px; color: #c9d1d9; font-size: 14px; resize: none; height: 50px; font-family: inherit; }
.chat-input button { margin-left: 10px; background: #f0f; color: #0d1117; border: none; border-radius: 8px; padding: 0 20px; font-weight: 600; cursor: pointer; font-size: 14px; }
.chat-input button:disabled { opacity: 0.5; cursor: wait; }

/* Loading */
.loading { text-align: center; padding: 40px; color: #484f58; }
</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-header">
    <h1>Sonya</h1>
    <span>Admin Panel</span>
  </div>
  <div class="nav">
    <div class="nav-item" data-page="providers">🔑 Providers</div>
    <div class="nav-item" data-page="usage">💸 Usage</div>
    <div class="nav-item" data-page="approvals">✋ Approvals</div>
    <div class="nav-item" data-page="tasks">📋 Tasks</div>
    <div class="nav-item active" data-page="dashboard">⚡ Dashboard</div>
    <div class="nav-item" data-page="operator">🎛️ Operator</div>
    <div class="nav-item" data-page="thoughts">💭 Thoughts</div>
    <div class="nav-item" data-page="memory">🧠 Memory</div>
    <div class="nav-item" data-page="telegram">📱 Telegram</div>
    <div class="nav-item" data-page="chat">💬 Chat</div>
    <div class="nav-item" data-page="audit">📋 Audit</div>
    <div class="nav-item" data-page="substrate">💾 Substrate</div>
    <div class="nav-item" data-page="selfmod">🔧 SelfMod</div>
    <div class="nav-item" data-page="core">⚙️ Core</div>
  </div>
  <div class="sidebar-footer">
    Sonya Environment v0.1<br>Package: tg-userbot
  </div>
</div>
<div class="main">
  <div class="topbar"><h2 id="page-title">Dashboard</h2></div>
  <div class="content" id="content"><div class="loading">Loading...</div></div>
</div>

<script>
const API = '';
let chatHistory = [];
let providersSnapshot = null;
let providersSelectedId = null;
let providersModelQuery = '';

document.querySelectorAll('.nav-item').forEach(el => {
  el.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    loadPage(el.dataset.page);
  });
});

async function loadPage(page) {
  document.getElementById('page-title').textContent = page.charAt(0).toUpperCase() + page.slice(1);
  const content = document.getElementById('content');
  content.innerHTML = '<div class="loading">Loading...</div>';

  if (page === 'chat') { renderChat(); return; }

  if (page === 'core') {
      try {
        const [statusResp, logsResp] = await Promise.all([
          fetch(`${API}/api/core/status`),
          fetch(`${API}/api/core/logs?lines=40`)
        ]);
        const status = await statusResp.json();
        const logs = await logsResp.json();
        content.innerHTML = renderers.core({...status, logs: logs.logs});
      } catch(e) {
        content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
      }
      return;
    }

    if (page === 'providers') {
      try {
        const resp = await fetch(`${API}/api/providers`);
        const data = await resp.json();
        content.innerHTML = renderers.providers(data);
      } catch(e) {
        content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
      }
      return;
    }

    if (page === 'usage') {
      try {
        const resp = await fetch(`${API}/api/llm_calls?limit=50`);
        const data = await resp.json();
        content.innerHTML = renderers.usage(data);
      } catch(e) {
        content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
      }
      return;
    }

    if (page === 'tasks') {
      try {
        const resp = await fetch(`${API}/api/tasks`);
        const data = await resp.json();
        content.innerHTML = renderers.tasks(data);
      } catch(e) {
        content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
      }
      return;
    }

    if (page === 'approvals') {
      try {
        const resp = await fetch(`${API}/api/approvals`);
        const data = await resp.json();
        content.innerHTML = renderers.approvals(data);
      } catch(e) {
        content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
      }
      return;
    }

    if (page === 'operator') {
      operatorStop();  // clear any previous polling
      try {
        const resp = await fetch(`${API}/api/operator/snapshot`);
        const data = await resp.json();
        content.innerHTML = renderers.operator(data);
        // Initialise live tail at the latest seq so we don't backfill 1000
        // historical events on first paint.
        operatorLastSeq = data.latest_seq || 0;
        operatorStart();  // begin live polling
      } catch(e) {
        content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
      }
      return;
    }

  if (page === 'selfmod') {
    try {
      const resp = await fetch(`${API}/api/selfmod/list`);
      const data = await resp.json();
      content.innerHTML = renderers.selfmod(data);
    } catch(e) {
      content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
    }
    return;
  }

  if (page === 'thoughts') {
    try {
      const kindsParam = thoughtsActiveKinds ? `?limit=200&kinds=${encodeURIComponent(thoughtsActiveKinds)}` : '?limit=200';
      const resp = await fetch(`${API}/api/thoughts${kindsParam}`);
      const data = await resp.json();
      content.innerHTML = renderers.thoughts(data);
    } catch(e) {
      content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
    }
    return;
  }

  try {
    const resp = await fetch(`${API}/api/${page}`);
    const data = await resp.json();
    content.innerHTML = renderers[page](data);
  } catch(e) {
    content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
  }
}

let thoughtsActiveKinds = '';
function thoughtsFilter(kinds) {
  thoughtsActiveKinds = kinds;
  loadPage('thoughts');
}

async function coreAction(action, mode) {
  try {
    const url = mode ? `${API}/api/core/${action}?mode=${mode}` : `${API}/api/core/${action}`;
    const resp = await fetch(url, {method: 'POST'});
    const data = await resp.json();
    alert(JSON.stringify(data));
    setTimeout(() => loadPage('core'), 2000);
  } catch(e) {
    alert('Error: ' + e.message);
  }
}

const renderers = {
  dashboard(d) {
    return `
      <div class="card"><h3>Subject State</h3>
        <div class="stat">Principal: <b>${d.state.active_principal || 'none'}</b></div>
        <div class="stat">Intentions: <b>${d.state.pending_intentions.length}</b></div>
        <div class="stat">Continuity Seq: <b>${d.latest_seq}</b></div>
      </div>
      <div class="card"><h3>Emotional Vector</h3>
        ${Object.entries(d.state.emotional_vector || {}).map(([k,v]) => `<div class="stat">${k}: <b>${v.toFixed(2)}</b></div>`).join('')}
      </div>
      <div class="card"><h3>Config</h3><pre>${JSON.stringify(d.config, null, 2)}</pre></div>`;
  },
  thoughts(d) {
    const events = d.events || [];
    if (events.length === 0) return '<div class="card"><h3>No events yet</h3></div>';

    // Filter UI
    const allKinds = Array.from(new Set(events.map(e => e.kind))).sort();
    const activeFilter = (d.kinds_filter || []).join(',');
    const filterChip = (k, label) => `
      <span class="chip ${activeFilter === k ? 'on' : ''}" onclick="thoughtsFilter('${k}')">${label}</span>`;

    const filterBar = `
      <div class="card" style="padding:10px">
        <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center">
          <span style="color:#8b949e;font-size:12px;margin-right:6px">Filter:</span>
          ${filterChip('', 'all')}
          ${filterChip('internal.thought', '💭 thoughts')}
          ${filterChip('internal.agent_step', '🔧 actions')}
          ${filterChip('incoming.telegram_message,outgoing.telegram_initiative,outgoing.telegram_progress,outgoing.response,outgoing.telegram_response', '💬 dialogue')}
          ${filterChip('internal.task_worker_tick,internal.task_worker_outcome,task.session_handoff,task.created,task.picked_up,task.step_done,task.failed,task.blocked,task.session_budget_exhausted', '📋 tasks')}
          ${filterChip('internal.tool_error,internal.task_worker_error', '⚠️ errors')}
          ${filterChip('internal.cognitive_tick,internal.agent_session_complete,internal.agent_session_outcome,internal.inbox_queued_during_session,internal.inbox_injected,internal.initiative_blocked,internal.capability_gap,internal.consolidation_run,subject.lifecycle.started,subject.lifecycle.stopped,self_mod.validation_layer_1,self_mod.validation_layer_2,self_mod.validation_layer_3,self_mod.validation_layer_4,approval.requested', '⚙️ system')}
        </div>
        <div style="font-size:11px;color:#6e7681;margin-top:6px">latest_seq=${d.latest_seq} • showing ${events.length}</div>
      </div>`;

    return filterBar + events.map(e => renderEvent(e)).join('');
  },
  memory(d) {
    let html = '<div class="card"><h3>Episodic (recent)</h3>';
    html += d.episodic.map(e => `<div class="event memory"><div class="meta">${e.event_type} • ${e.timestamp.slice(0,16)} • imp=${e.importance_score}</div><div class="body">${e.raw_content.slice(0,200)}</div></div>`).join('');
    html += '</div><div class="card"><h3>Semantic Facts</h3>';
    html += d.semantic.map(f => `<div class="event"><div class="meta">${f.fact_type} • conf=${f.confidence}</div><div class="body">${f.statement}</div></div>`).join('');
    html += '</div>';
    if (d.embedding_index) {
      const ei = d.embedding_index;
      let body;
      if (!ei.available) {
        body = `<div class="stat" style="color:#8b949e">embedder unavailable${ei.error ? ' — ' + ei.error : ''}</div>`;
      } else {
        const total = (ei.indexed || 0) + (ei.pending || 0);
        const pct = total > 0 ? Math.round((ei.indexed / total) * 100) : 100;
        body = `<div class="stat">Indexed: <b>${ei.indexed}</b></div>
                <div class="stat">Pending: <b>${ei.pending}</b></div>
                <div class="stat">Coverage: <b>${pct}%</b></div>`;
      }
      html = `<div class="card"><h3>Embedding Index</h3>${body}</div>` + html;
    }
    return html;
  },
  telegram(d) {
    if (!d.messages || d.messages.length === 0) return '<div class="card"><h3>No messages yet</h3><p>Userbot is running. Incoming messages will appear here.</p></div>';
    return `<div class="card"><h3>Recent Telegram Messages</h3>
      ${d.messages.map(m => `
        <div class="event ${m.is_private ? 'thought' : 'memory'}">
          <div class="meta">[${m.chat_id}] sender=${m.sender_id} • ${m.date}</div>
          <div class="body">${m.text}</div>
        </div>`).join('')}
    </div>`;
  },
  audit(d) {
    return d.entries.map(e => `
      <div class="event audit">
        <div class="meta">[${e.seq}] ${e.timestamp.slice(0,19)}</div>
        <div class="body">${e.action} → ${e.decision} (scope: ${e.scope})</div>
      </div>`).join('');
  },
  substrate(d) {
    return `<div class="card"><h3>Schema Version: ${d.version}</h3><pre>${d.path}</pre></div>
      <div class="card"><h3>Tables</h3>${d.tables.map(t => `<div class="stat">${t.name}: <b>${t.rows}</b></div>`).join('')}</div>`;
  },
  core(d) {
    const status = d.running ? '🟢 Running' : '🔴 Stopped';
    const pid = d.pid ? ` (PID: ${d.pid})` : '';
    return `
      <div class="card"><h3>Core Status</h3>
        <div class="stat">Status: <b>${status}${pid}</b></div>
        <p style="font-size:11px;color:#8b949e;margin-top:8px">Только один процесс может писать в substrate. Выбери режим.</p>
      </div>
      <div class="card"><h3>Start Modes</h3>
        <button onclick="coreAction('start','full')" style="background:#238636;color:white;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;margin:5px;font-size:14px">▶ Full (TG + Thinking)</button>
        <button onclick="coreAction('start','telegram_only')" style="background:#1f6feb;color:white;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;margin:5px;font-size:14px">📱 Telegram Only</button>
        <button onclick="coreAction('start','thinking_only')" style="background:#8957e5;color:white;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;margin:5px;font-size:14px">💭 Thinking Only</button>
      </div>
      <div class="card"><h3>Controls</h3>
        <button onclick="coreAction('stop')" style="background:#da3633;color:white;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;margin:5px;font-size:14px">⬛ Stop Core</button>
        <button onclick="loadPage('core')" style="background:#30363d;color:#c9d1d9;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;margin:5px;font-size:14px">🔄 Refresh</button>
      </div>
      <div class="card"><h3>Logs (last 40 lines)</h3><pre id="core-logs" style="font-size:11px;max-height:400px;overflow-y:auto">${d.logs || 'No logs'}</pre></div>`;
  },
  selfmod(d) {
    if (!d.proposals || d.proposals.length === 0) {
      return '<div class="card"><h3>No self-mod proposals yet</h3><p>When Sonya proposes changes to her own code via <code>selfmod.propose</code>, they appear here for review.</p></div>';
    }
    const statusColor = {
      draft: '#8b949e', validating: '#d29922', approved: '#3fb950', applied: '#3fb950',
      rejected: '#f85149', requires_governed_change: '#f0883e', governed_approved: '#3fb950',
      reverted: '#a371f7',
    };
    return `<div class="card"><h3>Self-modification proposals (${d.count})</h3>
      ${d.proposals.map(p => `
        <div class="event" style="border-left-color:${statusColor[p.status] || '#30363d'}">
          <div class="meta">[${p.proposal_id.slice(0,16)}...] ${p.target_module} • by ${p.proposed_by} • ${p.created_at.slice(0,19)}</div>
          <div class="body">${p.summary}</div>
          <div style="margin-top:8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span class="stat" style="background:${statusColor[p.status] || '#30363d'}33;color:${statusColor[p.status] || '#c9d1d9'}">${p.status}</span>
            <button onclick="selfmodView('${p.proposal_id}')" style="background:#30363d;color:#c9d1d9;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-size:12px">View diff</button>
            ${p.status === 'requires_governed_change' ? `
              <button onclick="selfmodAction('${p.proposal_id}','approve')" style="background:#238636;color:white;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-size:12px">✓ Approve</button>
              <button onclick="selfmodAction('${p.proposal_id}','deny')" style="background:#da3633;color:white;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-size:12px">✗ Deny</button>
            ` : ''}
          </div>
        </div>`).join('')}
    </div>`;
  },
  providers(d) {
    const s = d.settings || {};
    const keys = d.keys || [];
    const statusColor = {
      active: '#3fb950', cooldown: '#d29922', banned: '#f85149', disabled: '#8b949e',
    };
    const slotColor = {
      text: '#58a6ff', vision: '#a371f7', voice: '#d29922', video: '#f0883e', image_gen: '#3fb950',
    };
    const statusBadge = (st) => `<span style="background:${(statusColor[st]||'#30363d')}22;color:${statusColor[st]||'#c9d1d9'};padding:2px 8px;border-radius:3px;font-size:11px;font-weight:500">${st}</span>`;
    const slotBadge = (sl) => (sl || 'text').split(',').map(s => `<span style="background:${(slotColor[s.trim()]||'#30363d')}22;color:${slotColor[s.trim()]||'#c9d1d9'};padding:2px 6px;border-radius:3px;font-size:10px">${s.trim()}</span>`).join(' ');

    const settingsCard = `
      <div class="card"><h3>Default Provider</h3>
        <div style="display:grid;grid-template-columns:120px 1fr;gap:6px;font-size:13px;max-width:600px">
          <label>Provider:</label>
          <input id="prov-active" value="${s.active_provider || ''}" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
          <label>Model:</label>
          <input id="prov-model" value="${s.default_model || ''}" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
          <label>Base URL:</label>
          <input id="prov-base" value="${s.default_base_url || ''}" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
        </div>
        <button onclick="providersSaveSettings()" style="margin-top:10px;background:#238636;color:white;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;font-size:12px">Save</button>
        <span style="font-size:11px;color:#8b949e;margin-left:10px">hot-reload, рестарт не нужен</span>
      </div>`;

    const addCard = `
      <div class="card"><h3>Add key</h3>
        <div style="display:grid;grid-template-columns:100px 1fr 100px 1fr;gap:6px;font-size:12px;max-width:800px">
          <label>Provider:</label>
          <input id="add-provider" placeholder="fireworks / openrouter" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:5px;color:#c9d1d9;font-size:12px" />
          <label>Name:</label>
          <input id="add-name" placeholder="e.g. main" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:5px;color:#c9d1d9;font-size:12px" />
          <label>API key:</label>
          <input id="add-key" placeholder="fw_... / sk-or-..." type="password" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:5px;color:#c9d1d9;font-size:12px;grid-column:2/5" />
          <label>Model:</label>
          <input id="add-model" placeholder="empty = default" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:5px;color:#c9d1d9;font-size:12px" />
          <label>Base URL:</label>
          <input id="add-base" placeholder="empty = auto" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:5px;color:#c9d1d9;font-size:12px" />
          <label>Slot:</label>
          <input id="add-slot" value="text" placeholder="text,vision,voice,video,image_gen" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:5px;color:#c9d1d9;font-size:12px" />
          <label>Priority:</label>
          <input id="add-priority" type="number" value="0" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:5px;color:#c9d1d9;font-size:12px;width:60px" />
        </div>
        <div style="margin-top:8px;font-size:11px;color:#8b949e">Slot = для чего этот ключ. Несколько через запятую: <code>text,vision</code> = работает для обоих.</div>
        <button onclick="providersAddKey()" style="margin-top:8px;background:#238636;color:white;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;font-size:12px">Add</button>
      </div>`;

    const fmtBalance = (k) => {
      const b = k.balance || {};
      if (!b || (!b.ok && !b.monthly_spend_usd)) {
        if (b && b.error) return `<span style="color:#f85149" title="${b.error.replace(/"/g,'&quot;')}">err</span>`;
        return '';
      }
      const ms = b.monthly_spend_usd || {};
      const usage = (typeof ms.usage === 'number') ? ms.usage.toFixed(1) : '?';
      const limit = (typeof ms.limit === 'number') ? ms.limit.toFixed(0) : '?';
      const pct = (ms.usage && ms.limit) ? Math.round((ms.usage / ms.limit) * 100) : 0;
      const colour = pct > 80 ? '#f85149' : (pct > 50 ? '#d29922' : '#3fb950');
      return `<span style="color:${colour};font-size:11px">$${usage}/$${limit}</span>`;
    };

    // Group keys by provider
    const byProvider = {};
    keys.forEach(k => { (byProvider[k.provider] = byProvider[k.provider] || []).push(k); });

    let keysHtml = '';
    for (const [prov, pkeys] of Object.entries(byProvider)) {
      const activeCount = pkeys.filter(k => k.status === 'active').length;
      keysHtml += `<div class="card" style="padding:12px 16px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <h3 style="margin:0;font-size:13px">${prov} <span style="color:#8b949e;font-weight:400">(${activeCount}/${pkeys.length} active)</span></h3>
          ${prov === 'fireworks' ? '<button onclick="providersRefreshAll()" style="background:#1f6feb;color:white;border:none;padding:3px 8px;border-radius:3px;cursor:pointer;font-size:10px">↻ balances</button>' : ''}
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
        ${pkeys.map(k => `
          <div style="display:flex;align-items:center;gap:8px;padding:6px 8px;background:#0d1117;border-radius:4px;border-left:3px solid ${statusColor[k.status] || '#30363d'}">
            <div style="flex:1;min-width:0">
              <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
                <span style="font-size:12px;color:#c9d1d9;font-weight:500">${k.name}</span>
                <span style="font-size:10px;color:#6e7681">${k.key_masked}</span>
                ${statusBadge(k.status)}
                ${slotBadge(k.slot)}
                ${fmtBalance(k)}
                ${k.model ? '<span style="font-size:10px;color:#8b949e" title="model override">🎯 '+k.model.split('/').pop()+'</span>' : ''}
              </div>
              <div style="font-size:10px;color:#6e7681;margin-top:2px">
                ${k.request_count}req ${k.success_count}ok ${k.error_count}err
                ${k.last_used_at ? '• used '+k.last_used_at.slice(5,16) : ''}
                ${k.last_error ? '• <span style="color:#f85149" title="'+k.last_error.replace(/"/g,'&quot;')+'">⚠</span>' : ''}
              </div>
            </div>
            <div style="display:flex;gap:4px;flex-shrink:0">
              <button onclick="providersSetSlot('${k.key_id}','${k.slot}')" title="Change slot" style="background:#30363d;color:#c9d1d9;border:none;padding:3px 6px;border-radius:3px;cursor:pointer;font-size:10px">slot</button>
              <button onclick="providersTestKey('${k.key_id}')" title="Test" style="background:#1f6feb;color:white;border:none;padding:3px 6px;border-radius:3px;cursor:pointer;font-size:10px">test</button>
              ${k.status !== 'active' ? '<button onclick="providersSetStatus(\''+k.key_id+'\',\'active\')" style="background:#238636;color:white;border:none;padding:3px 6px;border-radius:3px;cursor:pointer;font-size:10px">on</button>' : '<button onclick="providersSetStatus(\''+k.key_id+'\',\'disabled\')" style="background:#6e7681;color:white;border:none;padding:3px 6px;border-radius:3px;cursor:pointer;font-size:10px">off</button>'}
              <button onclick="providersDeleteKey('${k.key_id}')" style="background:#da363322;color:#f85149;border:none;padding:3px 6px;border-radius:3px;cursor:pointer;font-size:10px">×</button>
            </div>
          </div>`).join('')}
        </div>
      </div>`;
    }

    if (keys.length === 0) {
      keysHtml = '<div class="card"><h3>No keys</h3><p style="color:#8b949e">Добавь хотя бы один ключ.</p></div>';
    }

    return settingsCard + addCard + keysHtml;
  },
  usage(d) {
    const t = d.totals || {};
    const rec = d.recent || [];
    const byPurpose = d.by_purpose_24h || [];
    const byModel = d.by_model_24h || [];
    const fmt = (n) => (n || 0).toLocaleString();
    const totalsCard = `
      <div class="card"><h3>Token Usage</h3>
        <div class="stat">last 1h: <b>${t.last_1h?.calls || 0}</b> calls / <b>${fmt(t.last_1h?.total_tokens)}</b> tokens</div>
        <div class="stat">last 24h: <b>${t.last_24h?.calls || 0}</b> calls / <b>${fmt(t.last_24h?.total_tokens)}</b> tokens</div>
        <div class="stat">all time: <b>${fmt(t.all_time?.calls)}</b> calls / <b>${fmt(t.all_time?.total_tokens)}</b> tokens</div>
        <div class="stat" style="background:#5d1421;color:#f85149">errors 24h: <b>${t.errors_24h || 0}</b></div>
      </div>`;
    const purposeCard = byPurpose.length ? `
      <div class="card"><h3>By purpose (24h)</h3>
        ${byPurpose.map(p => `<div class="stat">${p.purpose}: <b>${p.calls}</b> calls, <b>${fmt(p.tokens)}</b> tokens</div>`).join('')}
      </div>` : '';
    const modelCard = byModel.length ? `
      <div class="card"><h3>By model (24h)</h3>
        ${byModel.map(m => `<div class="stat">${m.model || '?'}: <b>${m.calls}</b> calls, <b>${fmt(m.tokens)}</b> tokens</div>`).join('')}
      </div>` : '';
    const recentCard = `
      <div class="card"><h3>Recent calls (last ${rec.length})</h3>
        ${rec.length === 0 ? '<p>No calls recorded yet.</p>' : rec.map(c => {
          const colour = c.status === 'ok' ? '#3fb950' : '#f85149';
          return `<div class="event" style="border-left-color:${colour}">
            <div class="meta">[${c.call_id}] ${c.timestamp.slice(0,19)} • ${c.provider}/${c.model.slice(-30)} • ${c.purpose}</div>
            <div class="body" style="font-size:12px">
              ${c.status === 'ok' ? `tokens: <b>${c.prompt_tokens}</b> in / <b>${c.completion_tokens}</b> out / <b>${c.total_tokens}</b> total` : `<span style="color:#f85149">status: ${c.status} (${c.http_status})${c.error ? ' — ' + c.error.slice(0,100) : ''}</span>`}
              <span style="color:#8b949e;margin-left:8px">${c.latency_ms}ms</span>
            </div>
          </div>`;
        }).join('')}
      </div>`;
    return totalsCard + purposeCard + modelCard + recentCard;
  },
  approvals(d) {
    const reqs = d.requests || [];
    if (reqs.length === 0) {
      return '<div class="card"><h3>No pending approvals</h3><p style="color:#8b949e">When Sonya tries shell.run / pip.install (без YOLO) — запрос появится здесь.</p></div>';
    }
    const fmtAction = (a) => {
      if (a.startsWith('shell.run:')) return '🖥️ shell.run';
      if (a.startsWith('pip.install:')) return '📦 pip.install';
      if (a.startsWith('governed_change:')) return '🔧 governed selfmod';
      return a;
    };
    return `<div class="card"><h3>Pending approvals (${reqs.length})</h3>
      ${reqs.map(r => `
        <div class="event" style="border-left-color:#d29922;margin-bottom:10px">
          <div class="meta">[${r.request_id.slice(5,21)}...] ${fmtAction(r.action)} • by ${r.principal_id} • ${r.created_at.slice(0,19)}</div>
          <div class="body" style="word-break:break-all"><code style="background:#0d1117;padding:4px 8px;border-radius:3px;color:#7ee787;display:inline-block;max-width:100%;white-space:pre-wrap">${(r.scope || '').replace(/</g,'&lt;').slice(0,400)}</code></div>
          <div style="margin-top:8px;display:flex;gap:6px">
            <button onclick="approvalsDecide('${r.request_id}','approve')" style="background:#238636;color:white;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;font-size:12px">✓ Approve</button>
            <button onclick="approvalsDecide('${r.request_id}','deny')" style="background:#da3633;color:white;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;font-size:12px">✗ Deny</button>
          </div>
        </div>`).join('')}
    </div>`;
  },
  operator(d) {
    const session = d.active_session;
    const lastPick = d.last_pick;
    const summary = d.open_tasks_summary || {};
    const drives = d.drives || {};
    const lastExt = d.last_external_trigger;
    const fmtTime = (s) => s ? s.slice(11, 19) : '—';
    const sessionCard = session ? `
      <div class="card" style="border-left:3px solid #3fb950">
        <h3>🔴 Active session</h3>
        <div style="font-size:13px;line-height:1.7">
          <div>Step <b>${session.current_step}</b> · tool <code style="background:#0d1117;padding:2px 6px;border-radius:3px;color:#7ee787">${session.current_tool || '(thought)'}</code></div>
          <div style="color:#8b949e">Started: ${fmtTime(session.started_at)} · last step: ${fmtTime(session.last_step_at)}</div>
          <div style="color:#8b949e">First seq: ${session.first_step_seq}</div>
        </div>
      </div>` : `
      <div class="card" style="border-left:3px solid #8b949e">
        <h3>💤 Idle</h3>
        <div style="color:#8b949e;font-size:13px">No active session right now. Last pick was ${lastPick ? `<b>${lastPick.chosen_kind}</b> at ${fmtTime(lastPick.at)}` : 'never'}.</div>
      </div>`;
    const driveBars = Object.entries(drives)
      .filter(([k]) => !k.startsWith('_'))
      .filter(([_, v]) => typeof v === 'number')
      .map(([k, v]) => {
        const pct = Math.min(100, Math.max(0, v * 100));
        const color = v > 0.7 ? '#f85149' : v > 0.4 ? '#d29922' : '#3fb950';
        return `<div style="margin:4px 0">
          <div style="display:flex;justify-content:space-between;font-size:11px;color:#8b949e"><span>${k}</span><span>${v.toFixed(2)}</span></div>
          <div style="background:#0d1117;height:6px;border-radius:3px;overflow:hidden"><div style="background:${color};height:100%;width:${pct}%"></div></div>
        </div>`;
      }).join('');
    const summaryCard = `
      <div class="card">
        <h3>📋 Tasks state</h3>
        <div style="display:flex;gap:14px;font-size:13px;flex-wrap:wrap">
          <span><b style="color:#3fb950">${summary.in_progress || 0}</b> in_progress</span>
          <span><b style="color:#d29922">${summary.blocked || 0}</b> blocked</span>
          <span><b style="color:#8b949e">${summary.pending || 0}</b> pending</span>
          <span><b style="color:#f85149">${summary.recently_failed_24h || 0}</b> failed 24h</span>
          <span><b style="color:#1f6feb">${d.approved_proposals_pending || 0}</b> APPROVED selfmod</span>
        </div>
      </div>`;
    const drivesCard = driveBars ? `
      <div class="card">
        <h3>🌡️ Drive counters</h3>
        ${driveBars}
      </div>` : '';
    const lastExtRow = lastExt ? `
      <div style="font-size:12px;color:#8b949e;margin-top:6px">
        Last external trigger: <code>${lastExt.reason}</code> at ${fmtTime(lastExt.at)} (seq=${lastExt.seq})
      </div>` : '';
    const triggerCard = `
      <div class="card">
        <h3>🎛️ Controls</h3>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
          <button onclick="operatorTriggerActive()" style="background:#1f6feb;color:white;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;font-size:13px">⚡ Force active session now</button>
          <button onclick="operatorInjectMessageDialog()" style="background:#6f42c1;color:white;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;font-size:13px">💬 Inject message (substrate)</button>
          <button onclick="loadPage('operator')" style="background:#30363d;color:#c9d1d9;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;font-size:13px">🔄 Refresh</button>
        </div>
        ${lastExtRow}
      </div>`;
    const recentPicks = (d.recent_picks || []).slice(0, 8);
    const picksCard = recentPicks.length ? `
      <div class="card">
        <h3>🧮 Recent scheduler picks</h3>
        <table style="width:100%;font-size:12px;border-collapse:collapse">
          <thead><tr style="color:#8b949e;text-align:left;border-bottom:1px solid #21262d">
            <th style="padding:6px 4px">When</th><th>Kind</th><th>Pri</th><th>Reason</th><th>Other ready</th>
          </tr></thead>
          <tbody>
            ${recentPicks.map(p => `<tr style="border-bottom:1px solid #161b22">
              <td style="padding:6px 4px;color:#8b949e">${fmtTime(p.at)}</td>
              <td><code style="background:#0d1117;padding:2px 6px;border-radius:3px;color:#7ee787">${p.chosen_kind}</code></td>
              <td><b>${p.chosen_priority}</b></td>
              <td>${p.chosen_reason || ''}</td>
              <td style="color:#8b949e">${(p.runners_up || []).map(r => `${r.kind}@${r.prio}`).join(', ') || '—'}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>` : '';
    const liveCard = `
      <div class="card">
        <h3>📜 Live event tail <span id="op-live-status" style="font-size:11px;color:#8b949e;font-weight:normal;margin-left:8px">connecting…</span></h3>
        <div id="op-live-feed" style="max-height:480px;overflow-y:auto;font-family:'Consolas',monospace;font-size:11px;line-height:1.5;background:#0d1117;border-radius:4px;padding:10px"></div>
      </div>`;
    return sessionCard + summaryCard + drivesCard + triggerCard + picksCard + liveCard;
  },
  tasks(d) {
    const tasks = d.tasks || [];
    if (tasks.length === 0) return '<div class="card"><h3>No tasks yet</h3></div>';
    const statusColor = {
      pending: '#8b949e', in_progress: '#3fb950', blocked: '#d29922',
      done: '#1f6feb', failed: '#f85149',
    };
    return `<div class="card"><h3>Tasks (${tasks.length})</h3>
      ${tasks.map(t => {
        const stepsLine = t.total_steps
          ? `<span>${t.completed_count}/${t.total_steps} steps</span>`
          : '';
        const sessionLine = (t.sessions_used || t.max_sessions)
          ? `<span style="color:#8b949e">⏵ ${t.sessions_used||0}/${t.max_sessions||'∞'} sessions</span>`
          : '';
        const nextHint = t.next_step_hint
          ? `<div style="margin-top:6px;font-size:12px;color:#79c0ff">→ next: ${escapeHtml(t.next_step_hint.slice(0,200))}</div>`
          : '';
        const lastNotes = t.last_session_notes
          ? `<div style="margin-top:4px;font-size:11px;color:#8b949e;white-space:pre-wrap">notes: ${escapeHtml(t.last_session_notes.slice(0,200))}</div>`
          : '';
        // Per-status action buttons. Failed/done tasks can be repurposed
        // (reset to pending). Blocked tasks can be unblocked. Open tasks
        // can be force-failed by operator. Delete is universal.
        const actBtn = (label, color, action) => `<button onclick="event.stopPropagation();taskAction('${t.task_id}','${action}')" style="background:${color}22;color:${color};border:1px solid ${color}55;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:11px;margin-left:4px">${label}</button>`;
        const actionButtons = [];
        if (t.status === 'blocked') {
          actionButtons.push(actBtn('🔓 unblock', '#3fb950', 'unblock'));
        }
        if (t.status === 'failed' || t.status === 'done') {
          actionButtons.push(actBtn('♻️ repurpose', '#1f6feb', 'repurpose'));
        }
        if (t.status === 'in_progress' || t.status === 'pending' || t.status === 'blocked') {
          actionButtons.push(actBtn('⏹ fail', '#d29922', 'fail'));
        }
        return `
        <div class="event task-card" style="border-left-color:${statusColor[t.status] || '#30363d'};cursor:pointer" onclick="taskToggle('${t.task_id}', this)">
          <div class="meta" style="display:flex;justify-content:space-between;align-items:center">
            <span>[${t.task_id}] ${t.created_by === 'ivan' ? '👤 Ivan' : '🤖 Sonya'} • ${t.notify_mode} • ${t.created_at.slice(0,19)}</span>
            <span>
              <span style="color:#8b949e;font-size:11px;margin-right:6px" class="task-toggle-arrow">▶</span>
              ${actionButtons.join('')}
              <button onclick="event.stopPropagation();taskDelete('${t.task_id}')" title="Delete task" style="background:#f8514922;color:#f85149;border:1px solid #f8514955;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:11px;margin-left:4px">✕ delete</button>
            </span>
          </div>
          <div class="body"><b>${escapeHtml(t.title)}</b>${t.description ? '<br><span style="color:#8b949e">' + escapeHtml(t.description.slice(0,200)) + '</span>' : ''}</div>
          <div style="margin-top:6px;font-size:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <span class="stat" style="background:${(statusColor[t.status]||'#30363d')}33;color:${statusColor[t.status]||'#c9d1d9'};padding:2px 8px;border-radius:3px">${t.status}</span>
            ${stepsLine}
            ${sessionLine}
            ${t.scheduled_for ? `<span style="color:#d29922">⏰ ${t.scheduled_for.slice(0,16)}</span>` : ''}
            ${t.blocker ? `<span style="color:#f85149">🔒 ${escapeHtml(t.blocker.slice(0,80))}</span>` : ''}
          </div>
          ${nextHint}
          ${lastNotes}
          ${t.result ? `<div style="margin-top:6px;font-size:12px;color:#7ee787">result: ${escapeHtml(t.result.slice(0,200))}</div>` : ''}
          <div class="task-detail" id="task-detail-${t.task_id}" style="display:none;margin-top:10px;padding-top:10px;border-top:1px solid #30363d"></div>
        </div>`;
      }).join('')}
    </div>`;
  }
};

async function taskDelete(taskId) {
  if (!confirm(`Delete task ${taskId}? This is permanent.`)) return;
  try {
    const resp = await fetch(`${API}/api/tasks/${taskId}`, {method:'DELETE'});
    const data = await resp.json();
    if (data.error) {
      alert('Error: ' + data.error);
      return;
    }
    setTimeout(() => loadPage('tasks'), 200);
  } catch(e) { alert('Error: ' + e.message); }
}

async function taskAction(taskId, action) {
  // operatorTaskAction lives at the bottom of the file (operator panel
  // shares the same backend endpoint). Reuse it so behavior stays
  // identical across both tabs.
  const promptText = {
    fail:      'Fail reason (will reach Ivan via TG for non-silent tasks):',
    unblock:   'New next_step hint (optional, blank to just clear blocker):',
    repurpose: 'Why repurpose this task (audit note, optional):',
  }[action] || 'Reason:';
  const reason = prompt(promptText, '');
  if (reason === null) return;  // cancelled
  try {
    const resp = await fetch(`${API}/api/operator/task/${taskId}/action`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action, reason: reason || ''}),
    });
    const data = await resp.json();
    if (resp.ok) {
      setTimeout(() => loadPage('tasks'), 200);
    } else {
      alert('Error: ' + JSON.stringify(data));
    }
  } catch(e) { alert('Error: ' + e.message); }
}

async function taskToggle(taskId, cardEl) {
  const detail = document.getElementById('task-detail-' + taskId);
  if (!detail) return;
  const arrow = cardEl.querySelector('.task-toggle-arrow');
  if (detail.style.display === 'block') {
    detail.style.display = 'none';
    if (arrow) arrow.textContent = '▶';
    return;
  }
  if (arrow) arrow.textContent = '▼';
  detail.style.display = 'block';
  // Skip refetch if already rendered (cheap toggle)
  if (detail.dataset.loaded === '1') return;
  detail.innerHTML = '<div style="color:#8b949e;font-size:12px">loading...</div>';
  try {
    const resp = await fetch(`${API}/api/tasks/${taskId}`);
    const t = await resp.json();
    if (t.error) {
      detail.innerHTML = `<div style="color:#f85149">${escapeHtml(t.error)}</div>`;
      return;
    }
    detail.innerHTML = renderTaskDetail(t);
    detail.dataset.loaded = '1';
  } catch(e) {
    detail.innerHTML = `<div style="color:#f85149">Error: ${escapeHtml(e.message)}</div>`;
  }
}

function renderTaskDetail(t) {
  // Plan steps with completion marks (if any). Plan_steps are voluntary —
  // tasks may have none and still be productive (continuity carried by
  // next_step_hint + last_session_notes from tasks.handoff).
  const completedIdx = new Set((t.completed_steps || []).map(s => s.step_idx));
  const stepsByIdx = new Map((t.completed_steps || []).map(s => [s.step_idx, s]));
  let stepsHtml = '';
  if ((t.plan_steps || []).length) {
    stepsHtml = '<div style="margin-bottom:10px"><b>Plan steps</b><ol style="margin:6px 0 0 22px;padding:0;line-height:1.6">';
    t.plan_steps.forEach((s, i) => {
      const done = completedIdx.has(i);
      const c = stepsByIdx.get(i);
      const summary = c && c.summary ? `<div style="font-size:11px;color:#8b949e;margin-left:0">${escapeHtml(c.summary.slice(0,300))}</div>` : '';
      const at = c && c.completed_at ? `<span style="font-size:10px;color:#6e7681;margin-left:6px">${c.completed_at.slice(0,19)}</span>` : '';
      stepsHtml += `<li style="${done ? 'color:#7ee787;text-decoration:line-through;text-decoration-color:#3fb95066' : 'color:#c9d1d9'}">${done ? '✓ ' : '○ '}${escapeHtml(s)}${at}${summary}</li>`;
    });
    stepsHtml += '</ol></div>';
  } else if ((t.completed_steps || []).length) {
    // Tasks without plan_steps but with logged step events — show flat list
    stepsHtml = '<div style="margin-bottom:10px"><b>Recorded steps</b><ul style="margin:6px 0 0 22px;padding:0;line-height:1.6">';
    t.completed_steps.forEach(c => {
      const at = c.completed_at ? `<span style="font-size:10px;color:#6e7681;margin-left:6px">${c.completed_at.slice(0,19)}</span>` : '';
      stepsHtml += `<li style="color:#7ee787">✓ ${escapeHtml((c.summary||'').slice(0,300))}${at}</li>`;
    });
    stepsHtml += '</ul></div>';
  }

  // Handoff history — most recent first.
  const handoffs = (t.events || [])
    .filter(e => e.kind === 'task.session_handoff' || e.kind === 'task.session_budget_exhausted')
    .reverse();
  let handoffHtml = '';
  if (handoffs.length) {
    handoffHtml = '<div style="margin-bottom:10px"><b>Session handoffs</b><div style="margin-top:6px">';
    handoffs.forEach(h => {
      const p = h.payload || {};
      const isExhausted = h.kind === 'task.session_budget_exhausted';
      const color = isExhausted ? '#f85149' : '#79c0ff';
      const label = isExhausted ? '🚫 budget exhausted' : `↪ session ${p.sessions_used||'?'}/${p.max_sessions||'∞'}`;
      handoffHtml += `<div style="border-left:2px solid ${color};padding:4px 10px;margin-bottom:6px;font-size:12px">
        <div style="color:${color}">${label} <span style="color:#6e7681;font-size:11px;margin-left:6px">${(h.created_at||'').slice(0,19)}</span></div>
        ${p.next_step ? `<div style="color:#c9d1d9;margin-top:2px">next: ${escapeHtml(String(p.next_step).slice(0,250))}</div>` : ''}
      </div>`;
    });
    handoffHtml += '</div></div>';
  }

  // Other lifecycle events (created, picked_up, blocked, completed, failed).
  const lifecycle = (t.events || [])
    .filter(e => !['task.session_handoff','task.session_budget_exhausted'].includes(e.kind));
  let lifecycleHtml = '';
  if (lifecycle.length) {
    lifecycleHtml = '<div><b>Lifecycle</b><div style="margin-top:6px;font-size:11px;color:#8b949e">';
    lifecycle.forEach(e => {
      const kindShort = e.kind.replace('task.', '');
      lifecycleHtml += `<div>· ${(e.created_at||'').slice(0,19)} <span style="color:#79c0ff">${kindShort}</span></div>`;
    });
    lifecycleHtml += '</div></div>';
  }

  // Long-form fields the list view truncated.
  const longFields = [
    t.next_step_hint && t.next_step_hint.length > 200 ? `<div style="margin-bottom:10px"><b>Next-step hint (full)</b><div style="margin-top:4px;color:#79c0ff;white-space:pre-wrap;font-size:12px">${escapeHtml(t.next_step_hint)}</div></div>` : '',
    t.last_session_notes && t.last_session_notes.length > 300 ? `<div style="margin-bottom:10px"><b>Last session notes (full)</b><div style="margin-top:4px;color:#8b949e;white-space:pre-wrap;font-size:12px">${escapeHtml(t.last_session_notes)}</div></div>` : '',
    t.result && t.result.length > 200 ? `<div style="margin-bottom:10px"><b>Result (full)</b><div style="margin-top:4px;color:#7ee787;white-space:pre-wrap;font-size:12px">${escapeHtml(t.result)}</div></div>` : '',
    t.blocker && t.blocker.length > 80 ? `<div style="margin-bottom:10px"><b>Blocker (full)</b><div style="margin-top:4px;color:#f85149;white-space:pre-wrap;font-size:12px">${escapeHtml(t.blocker)}</div></div>` : '',
  ].filter(Boolean).join('');

  return stepsHtml + handoffHtml + longFields + lifecycleHtml;
}

async function selfmodView(proposalId) {
  try {
    const resp = await fetch(`${API}/api/selfmod/${proposalId}`);
    const data = await resp.json();
    const win = window.open('', '_blank', 'width=900,height=700');
    win.document.write(`<html><head><title>Proposal ${proposalId}</title>
      <style>body{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:20px}
      h2{color:#f0f}pre{background:#161b22;padding:15px;border-radius:6px;overflow:auto;white-space:pre-wrap;word-break:break-all}</style>
      </head><body>
      <h2>${data.target_module}</h2>
      <p><b>Status:</b> ${data.status} | <b>By:</b> ${data.proposed_by} | <b>Created:</b> ${data.created_at}</p>
      <p><b>Summary:</b> ${data.summary}</p>
      <h3>diff_blob:</h3>
      <pre>${(data.diff_blob || '').replace(/</g,'&lt;')}</pre>
      </body></html>`);
  } catch(e) { alert('Error: ' + e.message); }
}

async function selfmodAction(proposalId, action) {
  if (!confirm(`${action.toUpperCase()} proposal ${proposalId.slice(0,16)}...?`)) return;
  try {
    const resp = await fetch(`${API}/api/selfmod/${proposalId}/${action}`, {method:'POST'});
    const data = await resp.json();
    alert(JSON.stringify(data, null, 2));
    setTimeout(() => loadPage('selfmod'), 500);
  } catch(e) { alert('Error: ' + e.message); }
}

renderers.providers = function(d) {
  const s=d.settings||{}, ps=d.providers||[], as=d.accounts||[], ms=d.models||[], qs=d.quota_windows||[], os=d.observations||[], ks=d.keys||[];
  providersSnapshot=d;
  if (!providersSelectedId || !ps.some(p=>p.provider_id===providersSelectedId)) providersSelectedId=s.active_provider||ps[0]?.provider_id||null;
  const available=new Set((d.available_models||[]).map(x=>x.model_id)), q=providersModelQuery.toLowerCase();
  const p=ps.find(x=>x.provider_id===providersSelectedId), pa=as.filter(x=>x.provider_id===providersSelectedId), rawPm=ms.filter(x=>x.provider===providersSelectedId);
  const pm=(p?.provider_id==='openrouter'&&!q)?rawPm.filter(x=>available.has(x.model_id)||(x.is_free&&x.discovery_source!=='manual')):rawPm;
  const shown=pm.filter(x=>!q||`${x.model_name} ${x.model_id} ${(x.strengths||[]).join(' ')}`.toLowerCase().includes(q));
  const badge=v=>`<span class="provider-badge ${escapeHtml(String(v||''))}">${escapeHtml(String(v||'unknown'))}</span>`;
  const summary=`<div class="provider-summary">
    <div class="card"><h3>Providers</h3><strong>${ps.length}</strong><span class="provider-meta">${ps.filter(x=>x.status==='active').length} active</span></div>
    <div class="card"><h3>Accounts</h3><strong>${as.length}</strong><span class="provider-meta">${as.filter(x=>x.status==='active').length} active</span></div>
    <div class="card"><h3>Model pool</h3><strong>${ms.length}</strong><span class="provider-meta">${available.size} available</span></div>
    <div class="card"><h3>Free models</h3><strong>${ms.filter(x=>x.is_free).length}</strong><span class="provider-meta">advertised</span></div>
    <div class="card"><h3>Observations</h3><strong>${os.length}</strong><span class="provider-meta">${qs.length} quota windows</span></div></div>`;
  const settings=`<div class="card"><h3>Runtime defaults</h3><div class="provider-form">
    <label>Active provider</label><select id="prov-active">${ps.map(x=>`<option value="${escapeHtml(x.provider_id)}" ${x.provider_id===s.active_provider?'selected':''}>${escapeHtml(x.display_name)} (${escapeHtml(x.provider_id)})</option>`).join('')}</select>
    <label>Default model</label><input id="prov-model" value="${escapeHtml(s.default_model||'')}" placeholder="provider/model">
    <label>Recovery base URL</label><input id="prov-base" value="${escapeHtml(s.default_base_url||'')}" placeholder="normally empty"></div>
    <div class="provider-actions" style="margin-top:10px"><button class="provider-button primary" onclick="providersSaveSettings()">Save defaults</button><span class="provider-meta">Substrate-owned; this does not define Sonya.</span></div></div>`;
  const pools=`<div class="card"><div class="provider-head"><h3>Provider pools</h3><button class="provider-button primary" onclick="providersCreateRegistry()">Add provider</button></div><div class="provider-stack">${ps.map(x=>{
    const ac=as.filter(a=>a.provider_id===x.provider_id).length, mc=ms.filter(m=>m.provider===x.provider_id).length;
    return `<div class="provider-row ${x.provider_id===providersSelectedId?'selected':''}" onclick="providersSelect('${x.provider_id}')"><div class="provider-head"><strong>${escapeHtml(x.display_name)}</strong>${badge(x.status)}</div><div class="provider-meta">${escapeHtml(x.provider_id)} · ${escapeHtml(x.adapter_kind)} · ${ac} accounts · ${mc} models</div></div>`;
  }).join('')||'<div class="provider-meta">No providers.</div>'}</div></div>`;
  const registry=p?`<div class="card"><div class="provider-head"><h3>Registry · ${escapeHtml(p.provider_id)}</h3><div class="provider-actions"><button class="provider-button primary" onclick="providersRefreshRegistry('${p.provider_id}')">Refresh / probe</button><button class="provider-button" onclick="providersEditRegistry('${p.provider_id}')">Edit</button><button class="provider-button danger" onclick="providersDeleteRegistry('${p.provider_id}')">Delete</button></div></div><div class="provider-form"><label>Name</label><span>${escapeHtml(p.display_name)}</span><label>Adapter</label><span>${escapeHtml(p.adapter_kind)}</span><label>Status</label><span>${badge(p.status)}</span><label>Base URL</label><span class="provider-meta">${escapeHtml(p.base_url||'not set')}</span></div></div>`:'';
  const accounts=p?`<div class="card"><div class="provider-head"><h3>Accounts · ${pa.length}</h3><button class="provider-button primary" onclick="providersAddAccount('${p.provider_id}')">Add account</button></div><div class="provider-stack">${pa.map(a=>`<div class="provider-row"><div class="provider-head"><div><strong>${escapeHtml(a.name)}</strong> ${badge(a.status)} ${badge('priority '+a.priority)}</div><div class="provider-actions"><button class="provider-button" onclick="providersRotateSecret('${a.account_id}')">Rotate secret</button><button class="provider-button" onclick="providersEditAccount('${a.account_id}')">Edit</button><button class="provider-button danger" onclick="providersDeleteAccount('${a.account_id}')">Delete</button></div></div><div class="provider-meta">${escapeHtml(a.account_id)} · ${escapeHtml(a.secret_masked||'no protected secret')} · ${escapeHtml(a.secret_ref||'no secret ref')}</div>${qs.filter(x=>x.account_id===a.account_id).map(x=>`<div class="provider-meta">${escapeHtml(x.quota_kind)}: ${x.remaining_value??'?'} / ${x.limit_value??'?'} ${escapeHtml(x.unit||'')} · reset ${escapeHtml(x.resets_at||'unknown')}</div>`).join('')}</div>`).join('')||'<div class="provider-meta">Create account metadata, then rotate its protected secret.</div>'}</div></div>`:'';
  const modelsTitle=(p?.provider_id==='openrouter'&&!q&&rawPm.length!==pm.length)?`Model pool · ${pm.length} free/requested of ${rawPm.length}`:`Model pool · ${pm.length}`;
  const models=p?`<div class="card"><div class="provider-head"><h3>${modelsTitle}</h3><input class="provider-filter" value="${escapeHtml(providersModelQuery)}" oninput="providersFilterModels(this.value)" placeholder="Filter models"></div><div class="provider-stack provider-models">${shown.map(m=>`<div class="provider-row"><div class="provider-head"><strong>${escapeHtml(m.model_name)}</strong><div>${m.is_free?badge('free'):''} ${badge(available.has(m.model_id)?'available':'unavailable')} ${m.text_loop_ok?'':badge('special worker')}</div></div><div class="provider-meta">${escapeHtml(m.model_id)} · context ${Number(m.context_length||0).toLocaleString()} · ${(m.modalities||[]).map(escapeHtml).join(', ')||'text'} · ${escapeHtml(m.discovery_source||'manual')}</div><div class="provider-actions" style="margin-top:6px"><button class="provider-button" onclick="providersSetOffering('${m.model_id}',true)">Enable for account</button><button class="provider-button" onclick="providersSetOffering('${m.model_id}',false)">Disable for account</button></div></div>`).join('')||'<div class="provider-meta">No matching models.</div>'}</div></div>`:'';
  const observations=p?`<div class="card"><h3>Recent observations</h3><div class="provider-stack">${os.filter(x=>x.provider_id===p.provider_id).map(x=>`<div class="provider-row"><div class="provider-head"><strong>${escapeHtml(x.observation_kind)}</strong>${badge(x.success?'active':'error')}</div><div class="provider-meta">${escapeHtml(x.observed_at||'')} · ${x.latency_ms??'?'} ms · ${escapeHtml(x.account_id||'provider-wide')} · ${escapeHtml(x.model_id||'n/a')}</div></div>`).join('')||'<div class="provider-meta">No observations yet.</div>'}</div></div>`:'';
  const legacy=`<details class="card provider-legacy"><summary>Legacy key compatibility (${ks.length})</summary><div class="provider-meta" style="margin:10px 0">Read-only migration/debug view. New credentials use protected provider-account secrets.</div>${ks.map(k=>`<div class="provider-row"><strong>${escapeHtml(k.provider)} / ${escapeHtml(k.name)}</strong><div class="provider-meta">${escapeHtml(k.key_masked)} · ${escapeHtml(k.status)} · legacy model ${escapeHtml(k.model||'none')}</div></div>`).join('')}</details>`;
  return summary+`<div class="provider-grid"><div>${settings}${pools}${legacy}</div><div>${registry}${accounts}${models}${observations}</div></div>`;
};

function providersRerender() { if (providersSnapshot) document.getElementById('content').innerHTML=renderers.providers(providersSnapshot); }
function providersSelect(id) { providersSelectedId=id; providersRerender(); }
function providersFilterModels(value) { providersModelQuery=value; providersRerender(); }
async function providersJson(url, body) {
  const resp=await fetch(`${API}${url}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
  const data=await resp.json(); if(!resp.ok) throw new Error(`${resp.status}: ${JSON.stringify(data)}`); return data;
}
async function providersCreateRegistry() {
  const provider_id=prompt('Provider ID:'); if(!provider_id)return; const display_name=prompt('Display name:',provider_id)||provider_id;
  const adapter_kind=prompt('Adapter kind:','openai_compatible')||'openai_compatible'; const base_url=prompt('Base URL:','')||'';
  try{await providersJson('/api/providers/registry',{provider_id,display_name,adapter_kind,base_url,status:'active'});providersSelectedId=provider_id.toLowerCase();loadPage('providers');}catch(e){alert(e.message);}
}
async function providersEditRegistry(id) {
  const p=providersSnapshot.providers.find(x=>x.provider_id===id); const display_name=prompt('Display name:',p.display_name); if(display_name===null)return;
  const status=prompt('Status:',p.status); if(status===null)return; const base_url=prompt('Base URL:',p.base_url||''); if(base_url===null)return;
  try{await providersJson(`/api/providers/registry/${id}`,{provider_id:id,display_name,adapter_kind:p.adapter_kind,status,base_url,capabilities:p.capabilities,constraints:p.constraints,metadata:p.metadata});loadPage('providers');}catch(e){alert(e.message);}
}
async function providersDeleteRegistry(id) { if(!confirm(`Delete provider ${id}?`))return; try{await providersJson(`/api/providers/registry/${id}/delete`,{});loadPage('providers');}catch(e){alert(e.message);} }
async function providersRefreshRegistry(id) { try{const data=await providersJson(`/api/providers/registry/${id}/refresh`,{});alert(`Refresh ${id}: ${data.ok?'ok':'failed'}, ${data.models_seen} models, ${data.quotas_seen} quotas${data.error?' · '+data.error:''}`);loadPage('providers');}catch(e){alert(e.message);} }
async function providersAddAccount(provider_id) {
  const name=prompt('Account name:'); if(!name)return; const priority=parseInt(prompt('Priority:','0')||'0');
  try{await providersJson('/api/providers/accounts',{provider_id,name,priority,status:'active'});loadPage('providers');}catch(e){alert(e.message);}
}
async function providersEditAccount(id) {
  const a=providersSnapshot.accounts.find(x=>x.account_id===id); const name=prompt('Account name:',a.name); if(name===null)return;
  const status=prompt('Status:',a.status); if(status===null)return; const priority=parseInt(prompt('Priority:',String(a.priority))||'0');
  try{await providersJson(`/api/providers/accounts/${id}`,{name,status,priority,constraints:a.constraints,metadata:a.metadata});loadPage('providers');}catch(e){alert(e.message);}
}
async function providersDeleteAccount(id) { if(!confirm(`Delete account ${id}?`))return; try{await providersJson(`/api/providers/accounts/${id}/delete`,{});loadPage('providers');}catch(e){alert(e.message);} }
async function providersRotateSecret(id) {
  const secret=prompt('New credential (sent only to protected ingestion endpoint):'); if(!secret)return;
  try{const resp=await fetch(`${API}/api/providers/accounts/${id}/secret`,{method:'PUT',headers:{'Content-Type':'application/octet-stream'},body:secret});const data=await resp.json();if(!resp.ok)throw new Error(`${resp.status}: ${JSON.stringify(data)}`);loadPage('providers');}catch(e){alert(e.message);}
}
async function providersSetOffering(model_id,enabled) {
  const candidates=(providersSnapshot.accounts||[]).filter(x=>x.provider_id===providersSelectedId); if(!candidates.length){alert('Create an account first.');return;}
  const account_id=prompt(`Account ID for ${enabled?'enable':'disable'}:`,candidates[0].account_id); if(!account_id)return;
  try{await providersJson('/api/providers/accounts/offerings',{account_id,model_id,enabled,metadata:{source:'manual_admin',requested:enabled}});loadPage('providers');}catch(e){alert(e.message);}
}

async function providersSaveSettings() {
  const body = {
    active_provider: document.getElementById('prov-active').value.trim(),
    default_model: document.getElementById('prov-model').value.trim(),
    default_base_url: document.getElementById('prov-base').value.trim(),
  };
  try {
    const resp = await fetch(`${API}/api/providers/settings`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (resp.ok) loadPage('providers');
    else alert(`Error ${resp.status}: ${JSON.stringify(data)}`);
  } catch(e) { alert('Error: ' + e.message); }
}

async function providersAddKey() {
  const body = {
    provider: document.getElementById('add-provider').value.trim(),
    name: document.getElementById('add-name').value.trim(),
    api_key: document.getElementById('add-key').value.trim(),
    base_url: document.getElementById('add-base').value.trim(),
    model: document.getElementById('add-model').value.trim(),
    priority: parseInt(document.getElementById('add-priority').value || '0'),
    slot: document.getElementById('add-slot').value.trim() || 'text',
  };
  if (!body.provider || !body.name || !body.api_key) {
    alert('provider, name, api_key required');
    return;
  }
  try {
    const resp = await fetch(`${API}/api/providers/keys`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (resp.ok) {
      loadPage('providers');
    } else {
      alert(`Error ${resp.status}: ${JSON.stringify(data)}`);
    }
  } catch(e) { alert('Error: ' + e.message); }
}

async function providersDeleteKey(keyId) {
  if (!confirm(`Delete key ${keyId}?`)) return;
  try {
    const resp = await fetch(`${API}/api/providers/keys/${keyId}/delete`, {method:'POST'});
    const data = await resp.json();
    if (resp.ok) loadPage('providers'); else alert(`Error: ${JSON.stringify(data)}`);
  } catch(e) { alert('Error: ' + e.message); }
}

async function providersSetSlot(keyId, currentSlot) {
  const newSlot = prompt(`Slot for this key (comma-separated: text,vision,voice,video,image_gen):`, currentSlot || 'text');
  if (newSlot === null) return;
  try {
    const resp = await fetch(`${API}/api/providers/keys/${keyId}`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({slot: newSlot.trim()}),
    });
    const data = await resp.json();
    if (resp.ok) loadPage('providers'); else alert(`Error: ${JSON.stringify(data)}`);
  } catch(e) { alert('Error: ' + e.message); }
}

async function providersTestKey(keyId) {
  try {
    const resp = await fetch(`${API}/api/providers/keys/${keyId}/test`, {method:'POST'});
    const data = await resp.json();
    alert(JSON.stringify(data, null, 2));
  } catch(e) { alert('Error: ' + e.message); }
}

async function providersSetStatus(keyId, status) {
  try {
    const resp = await fetch(`${API}/api/providers/keys/${keyId}/status`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({status}),
    });
    const data = await resp.json();
    if (resp.ok) loadPage('providers'); else alert(`Error: ${JSON.stringify(data)}`);
  } catch(e) { alert('Error: ' + e.message); }
}

async function providersRefreshOne(keyId) {
  try {
    const resp = await fetch(`${API}/api/providers/keys/${keyId}/balance/refresh`, {method:'POST'});
    const data = await resp.json();
    if (resp.ok) loadPage('providers'); else alert(`Error: ${JSON.stringify(data)}`);
  } catch(e) { alert('Error: ' + e.message); }
}

async function providersRefreshAll() {
  try {
    const resp = await fetch(`${API}/api/providers/balance/refresh`, {method:'POST'});
    const data = await resp.json();
    if (resp.ok) loadPage('providers'); else alert(`Error: ${JSON.stringify(data)}`);
  } catch(e) { alert('Error: ' + e.message); }
}

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function eventClass(kind) {
  if (kind === 'internal.thought') return 'thought';
  if (kind === 'internal.agent_step') return 'action';
  if (kind === 'incoming.telegram_message') return 'dialog-in';
  if (kind.startsWith('outgoing.')) return 'dialog-out';
  if (kind.endsWith('_error') || kind.includes('error')) return 'error';
  if (kind.startsWith('task.') || kind.startsWith('internal.task_')) return 'task';
  return 'system';
}

function eventIcon(kind) {
  if (kind === 'internal.thought') return '💭';
  if (kind === 'internal.agent_step') return '🔧';
  if (kind === 'incoming.telegram_message') return '📨';
  if (kind === 'outgoing.telegram_initiative') return '📤';
  if (kind.startsWith('outgoing.')) return '📤';
  if (kind.endsWith('_error') || kind.includes('error')) return '⚠️';
  if (kind.startsWith('task.')) return '📋';
  if (kind === 'internal.task_worker_tick') return '⚙️';
  if (kind === 'internal.task_worker_outcome') return '✅';
  if (kind === 'internal.cognitive_tick') return '🧠';
  if (kind === 'internal.agent_session_complete') return '⏹️';
  if (kind === 'internal.agent_session_outcome') return '⏹️';
  if (kind === 'subject.lifecycle.started') return '▶️';
  if (kind === 'subject.lifecycle.stopped') return '⏸️';
  if (kind === 'approval.requested') return '✋';
  if (kind === 'internal.initiative_blocked') return '🚫';
  if (kind === 'internal.capability_gap') return '🔍';
  if (kind.startsWith('self_mod.')) return '🔧';
  return '·';
}

function renderEvent(e) {
  const cls = eventClass(e.kind);
  const icon = eventIcon(e.kind);
  const p = e.payload || {};
  const time = (e.created_at || '').slice(11, 19);
  const date = (e.created_at || '').slice(0, 10);
  const seqId = `raw-${e.seq}`;

  // Body — kind-specific friendly rendering.
  let body = '';

  if (e.kind === 'internal.thought') {
    const text = p.thought || p.content || '';
    body = `<div class="text">${escapeHtml(text)}</div>`;

  } else if (e.kind === 'incoming.telegram_message') {
    body = `<div class="text">${escapeHtml(p.text || '')}</div>`;

  } else if (e.kind === 'outgoing.telegram_initiative' || e.kind.startsWith('outgoing.')) {
    body = `<div class="text">${escapeHtml(p.text || '')}</div>`;

  } else if (e.kind === 'internal.agent_step') {
    const step = p.step;
    const type = p.type;
    if (type === 'action') {
      const tool = p.tool || '?';
      const arg = (p.arg || '').slice(0, 200);
      const thought = p.thought || '';
      body = `<div class="tool-line">step ${step} → ${escapeHtml(tool)}(${escapeHtml(arg)})</div>`;
      if (thought) {
        body += `<div class="text" style="margin-top:6px">${escapeHtml(thought.slice(0, 600))}</div>`;
      }
    } else if (type === 'thought') {
      body = `<div class="text">step ${step}: ${escapeHtml((p.content || '').slice(0, 600))}</div>`;
    } else if (type === 'done') {
      body = `<div class="text">[DONE step ${step}] ${escapeHtml((p.content || '').slice(0, 600))}</div>`;
    } else {
      body = `<div class="text">${escapeHtml(JSON.stringify(p).slice(0, 300))}</div>`;
    }

  } else if (e.kind === 'internal.task_worker_tick') {
    body = `<div class="text">tick task=<b>${escapeHtml(p.task_id || '?')}</b> "${escapeHtml(p.title || '')}" → ${escapeHtml(p.next_step || '')}</div>`;

  } else if (e.kind === 'internal.task_worker_outcome') {
    const acts = (p.actions || []).slice(0, 3).map(a => escapeHtml(a.slice(0, 60))).join(' · ');
    body = `<div class="text">${p.steps} steps · actions: ${acts || '(none)'}${p.budget_exceeded ? ' · ⏱ budget' : ''}</div>`;

  } else if (e.kind === 'internal.task_worker_error') {
    body = `<div class="text">task=<b>${escapeHtml(p.task_id || '?')}</b><br><span style="color:#f85149">${escapeHtml((p.error || '').slice(0, 300))}</span></div>`;

  } else if (e.kind === 'internal.tool_error') {
    body = `<div class="text">tool=<b>${escapeHtml(p.tool || '?')}</b> arg=${escapeHtml((p.arg || '').slice(0, 80))}<br><span style="color:#f85149">${escapeHtml((p.error_message || '').slice(0, 300))}</span></div>`;

  } else if (e.kind === 'internal.agent_session_complete' || e.kind === 'internal.agent_session_outcome') {
    const acts = (p.actions || []).slice(0, 5).map(a => escapeHtml(a.slice(0, 50))).join(' · ');
    const summary = p.summary && p.summary !== '(see prior agent_step)' ? `<div class="text" style="margin-top:6px">${escapeHtml(String(p.summary).slice(0, 400))}</div>` : '';
    body = `<div class="text">${p.steps || 0} steps · ${acts || '(no tools)'}${p.budget_exceeded ? ' · ⏱ budget' : ''}</div>${summary}`;

  } else if (e.kind === 'internal.cognitive_tick') {
    const triggers = (p.triggers || []).join(', ');
    const counters = p.counters ? Object.entries(p.counters).map(([k, v]) => `${k}=${(+v).toFixed(2)}`).join(' ') : '';
    body = `<div class="observation-line">tick ${p.tick} · ${triggers || 'no triggers'} · ${counters}</div>`;

  } else if (e.kind === 'internal.inbox_queued_during_session' || e.kind === 'internal.inbox_injected') {
    body = `<div class="text">${escapeHtml((p.preview || '').slice(0, 200))}</div>`;

  } else if (e.kind === 'internal.initiative_blocked') {
    body = `<div class="text"><b>blocked:</b> ${escapeHtml(p.reason || '?')} — preview: ${escapeHtml((p.preview || '').slice(0, 200))}</div>`;

  } else if (e.kind === 'task.session_handoff') {
    body = `<div class="text">task=<b>${escapeHtml(p.task_id || '?')}</b> · sessions ${p.sessions_used}/${p.max_sessions || '∞'}<br>next: ${escapeHtml((p.next_step || '').slice(0, 200))}</div>`;

  } else if (e.kind.startsWith('task.')) {
    const tid = p.task_id || '?';
    body = `<div class="text">task=<b>${escapeHtml(tid)}</b> · ${escapeHtml(JSON.stringify(p).slice(0, 200))}</div>`;

  } else {
    // Generic fallback — short JSON line
    const compact = Object.entries(p).slice(0, 4)
      .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v).slice(0, 60) : String(v).slice(0, 60)}`)
      .join(' · ');
    body = `<div class="observation-line">${escapeHtml(compact)}</div>`;
  }

  return `
    <div class="event ${cls}">
      <div class="meta">${icon} <b>${escapeHtml(e.kind)}</b> · ${date} ${time} · seq=${e.seq}</div>
      <div class="body">
        ${body}
        <div class="raw-toggle" onclick="this.nextElementSibling.classList.toggle('show')">▸ raw payload</div>
        <pre class="raw">${escapeHtml(JSON.stringify(p, null, 2))}</pre>
      </div>
    </div>`;
}

async function approvalsDecide(reqId, decision) {
  try {
    const resp = await fetch(`${API}/api/approvals/${reqId}/${decision}`, {method:'POST'});
    const data = await resp.json();
    if (resp.ok) loadPage('approvals'); else alert(`Error ${resp.status}: ${JSON.stringify(data)}`);
  } catch(e) { alert('Error: ' + e.message); }
}

function renderChat() {
  const content = document.getElementById('content');
  content.innerHTML = `<div class="chat-container">
    <div class="chat-messages" id="chat-msgs">${chatHistory.map(m => `<div class="chat-msg ${m.role}">${m.text}</div>`).join('')}</div>
    <div class="chat-input">
      <textarea id="chat-in" placeholder="Напиши Соне..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat()}"></textarea>
      <button id="chat-btn" onclick="sendChat()">→</button>
    </div>
  </div>`;
}

async function sendChat() {
  const input = document.getElementById('chat-in');
  const btn = document.getElementById('chat-btn');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  btn.disabled = true;
  chatHistory.push({role:'user', text:msg});
  renderChat();
  document.getElementById('chat-msgs').scrollTop = 99999;

  try {
    const resp = await fetch(`${API}/api/chat/send`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: msg})
    });
    const data = await resp.json();
    chatHistory.push({role:'sonya', text: data.response});
  } catch(e) {
    chatHistory.push({role:'sonya', text: `[Error: ${e.message}]`});
  }
  btn.disabled = false;
  renderChat();
  document.getElementById('chat-msgs').scrollTop = 99999;
}

// --- Operator panel: live polling + controls -------------------------
let operatorLastSeq = 0;
let operatorPollTimer = null;

function operatorStop() {
  if (operatorPollTimer) {
    clearTimeout(operatorPollTimer);
    operatorPollTimer = null;
  }
}

function operatorStart() {
  operatorStop();
  operatorTick();
}

async function operatorTick() {
  // If user navigated away, stop polling.
  const feed = document.getElementById('op-live-feed');
  if (!feed) {
    operatorStop();
    return;
  }
  try {
    const resp = await fetch(`${API}/api/operator/live?since=${operatorLastSeq}&limit=80`);
    const data = await resp.json();
    const events = data.events || [];
    if (events.length > 0) {
      const html = events.map(operatorRenderEvent).join('');
      feed.insertAdjacentHTML('beforeend', html);
      // Keep only last ~400 entries to bound DOM size
      while (feed.children.length > 400) feed.removeChild(feed.firstChild);
      feed.scrollTop = feed.scrollHeight;
      operatorLastSeq = events[events.length - 1].seq;
    }
    const status = document.getElementById('op-live-status');
    if (status) {
      const stamp = new Date().toLocaleTimeString();
      status.textContent = `live · last poll ${stamp} · seq ${operatorLastSeq}`;
      status.style.color = '#3fb950';
    }
  } catch (e) {
    const status = document.getElementById('op-live-status');
    if (status) {
      status.textContent = 'poll error: ' + e.message;
      status.style.color = '#f85149';
    }
  }
  // 3s poll cadence keeps cost low while still feeling live
  operatorPollTimer = setTimeout(operatorTick, 3000);
}

function operatorRenderEvent(e) {
  const t = (e.at || '').slice(11, 19);
  const seq = e.seq;
  const kind = e.kind || '';
  const d = e.data || {};
  let icon = '·', color = '#8b949e', body = '';
  if (kind === 'internal.agent_step') {
    if (d.type === 'action') {
      icon = '🔧';
      color = '#7ee787';
      body = `step ${d.step} · <b>${d.tool}</b> ${d.arg ? '<span style="color:#8b949e">' + escapeHtml(d.arg.slice(0, 120)) + '</span>' : ''}`;
    } else if (d.type === 'done') {
      icon = '✅';
      color = '#3fb950';
      body = `[DONE] ${escapeHtml((d.content || '').slice(0, 200))}`;
    } else {
      icon = '💭';
      body = escapeHtml((d.content || d.thought || '').slice(0, 200));
    }
  } else if (kind === 'internal.scheduler_pick') {
    icon = '🎯';
    color = '#79c0ff';
    body = `pick: <b>${d.chosen_kind}</b> @${d.chosen_priority} (${d.chosen_reason || ''}) · ${d.runners_count || 0} other ready`;
  } else if (kind === 'internal.blocker_detected') {
    icon = '⚠️';
    color = '#d29922';
    body = `blocker [${d.blocker_kind}] on ${d.tool}: ${escapeHtml((d.preview || '').slice(0, 150))}`;
  } else if (kind.startsWith('outgoing.')) {
    icon = '➡️';
    color = '#1f6feb';
    body = `→ ${escapeHtml((d.text || '').slice(0, 240))}`;
  } else if (kind.startsWith('incoming.')) {
    icon = '⬅️';
    color = '#a371f7';
    body = `← ${escapeHtml((d.text || '').slice(0, 240))}`;
  } else if (kind.startsWith('task.')) {
    icon = '📋';
    color = '#d29922';
    body = `${kind.slice(5)} · ${d.task_id || ''} · ${escapeHtml((d.next_step || '').slice(0, 120))}`;
  } else if (kind === 'internal.agent_session_complete') {
    icon = '🏁';
    color = '#7ee787';
    body = `session complete (${kind})`;
  } else if (kind === 'self_mod.applied' || kind === 'self_mod.git_pushed') {
    icon = '🔧';
    color = '#3fb950';
    body = `${kind}: ${JSON.stringify(d).slice(0, 200)}`;
  } else {
    body = `${kind}`;
  }
  return `<div style="display:flex;gap:8px;margin-bottom:3px">
    <span style="color:#484f58;flex-shrink:0">${t}</span>
    <span style="flex-shrink:0">${icon}</span>
    <span style="color:${color};flex:1;word-break:break-word">${body}</span>
    <span style="color:#484f58;flex-shrink:0;font-size:10px">${seq}</span>
  </div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

async function operatorTriggerActive() {
  const reason = prompt('Reason for the trigger (audit label)?', 'manual_admin');
  if (reason === null) return;
  try {
    const resp = await fetch(`${API}/api/operator/trigger-active`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({reason: reason || 'manual_admin'}),
    });
    const data = await resp.json();
    alert(`Triggered.\nseq=${data.event_seq}\n${data.note || ''}`);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function operatorInjectMessageDialog() {
  const text = prompt(
    'Inject as Ivan-message (substrate-only — won\'t trigger TG reply by itself, ' +
    'but the next active session will see it as recent context):'
  );
  if (!text) return;
  try {
    const resp = await fetch(`${API}/api/operator/inject-message`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text}),
    });
    const data = await resp.json();
    alert(`Injected.\nseq=${data.event_seq}\n${data.note || ''}`);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function operatorTaskAction(taskId, action) {
  let reason = '';
  if (action !== 'delete') {
    reason = prompt(`${action.toUpperCase()} task ${taskId.slice(0, 16)}... reason?`, '') || '';
  } else {
    if (!confirm(`Delete task ${taskId}?`)) return;
  }
  try {
    const resp = await fetch(`${API}/api/operator/task/${taskId}/action`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action, reason}),
    });
    const data = await resp.json();
    if (resp.ok) {
      loadPage('operator');
    } else {
      alert(`Error: ${JSON.stringify(data)}`);
    }
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

loadPage('dashboard');
</script>
</body>
</html>"""
