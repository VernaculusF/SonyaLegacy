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
          ${filterChip('incoming.telegram_message,outgoing.telegram_initiative,outgoing.response,outgoing.telegram_response', '💬 dialogue')}
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
  tasks(d) {
    const tasks = d.tasks || [];
    if (tasks.length === 0) return '<div class="card"><h3>No tasks yet</h3></div>';
    const statusColor = {
      pending: '#8b949e', in_progress: '#3fb950', blocked: '#d29922',
      done: '#1f6feb', failed: '#f85149',
    };
    return `<div class="card"><h3>Tasks (${tasks.length})</h3>
      ${tasks.map(t => `
        <div class="event" style="border-left-color:${statusColor[t.status] || '#30363d'}">
          <div class="meta" style="display:flex;justify-content:space-between;align-items:center">
            <span>[${t.task_id}] ${t.created_by === 'ivan' ? '👤 Ivan' : '🤖 Sonya'} • ${t.notify_mode} • ${t.created_at.slice(0,19)}</span>
            <button onclick="taskDelete('${t.task_id}')" title="Delete task" style="background:#f8514922;color:#f85149;border:1px solid #f8514955;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:11px">✕ delete</button>
          </div>
          <div class="body"><b>${t.title}</b>${t.description ? '<br><span style="color:#8b949e">' + t.description.slice(0,200) + '</span>' : ''}</div>
          <div style="margin-top:6px;font-size:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <span class="stat" style="background:${(statusColor[t.status]||'#30363d')}33;color:${statusColor[t.status]||'#c9d1d9'};padding:2px 8px;border-radius:3px">${t.status}</span>
            ${t.total_steps ? `<span>${t.completed_count}/${t.total_steps} steps</span>` : ''}
            ${t.scheduled_for ? `<span style="color:#d29922">⏰ ${t.scheduled_for.slice(0,16)}</span>` : ''}
            ${t.blocker ? `<span style="color:#f85149">🔒 ${t.blocker.slice(0,80)}</span>` : ''}
          </div>
          ${t.result ? `<div style="margin-top:6px;font-size:12px;color:#7ee787">result: ${t.result.slice(0,200)}</div>` : ''}
        </div>`).join('')}
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

loadPage('dashboard');
</script>
</body>
</html>"""
