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
.event .meta { color: #484f58; font-size: 11px; margin-bottom: 4px; }
.event .body { color: #c9d1d9; }

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

  try {
    const resp = await fetch(`${API}/api/${page}`);
    const data = await resp.json();
    content.innerHTML = renderers[page](data);
  } catch(e) {
    content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
  }
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
    return d.events.map(e => `
      <div class="event ${e.kind.includes('internal') ? 'thought' : ''}">
        <div class="meta">[${e.seq}] ${e.kind} • ${e.created_at.slice(0,19)}</div>
        <div class="body"><pre>${JSON.stringify(e.payload, null, 2).slice(0,500)}</pre></div>
      </div>`).join('');
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
    const statusBadge = (st) => `<span class="stat" style="background:${(statusColor[st]||'#30363d')}33;color:${statusColor[st]||'#c9d1d9'};padding:3px 8px;border-radius:4px;font-size:11px">${st}</span>`;

    const settingsCard = `
      <div class="card"><h3>Active Provider</h3>
        <div style="display:grid;grid-template-columns:140px 1fr;gap:8px;font-size:13px">
          <label>Provider:</label>
          <input id="prov-active" value="${s.active_provider || ''}" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
          <label>Default model:</label>
          <input id="prov-model" value="${s.default_model || ''}" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
          <label>Default base URL:</label>
          <input id="prov-base" value="${s.default_base_url || ''}" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
        </div>
        <button onclick="providersSaveSettings()" style="margin-top:10px;background:#238636;color:white;border:none;padding:8px 16px;border-radius:4px;cursor:pointer">Save settings</button>
        <p style="font-size:11px;color:#8b949e;margin-top:8px">Stop core before changing. After save — start core back.</p>
      </div>`;

    const addCard = `
      <div class="card"><h3>Add new key</h3>
        <div style="display:grid;grid-template-columns:140px 1fr;gap:6px;font-size:13px">
          <label>Provider:</label>
          <input id="add-provider" placeholder="fireworks / openrouter / groq / ..." style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
          <label>Name:</label>
          <input id="add-name" placeholder="e.g. main / kikicide" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
          <label>API key:</label>
          <input id="add-key" placeholder="fw_... or sk-..." type="password" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
          <label>Base URL (optional):</label>
          <input id="add-base" placeholder="leave empty for provider default" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
          <label>Model override (optional):</label>
          <input id="add-model" placeholder="leave empty for default_model" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
          <label>Priority:</label>
          <input id="add-priority" type="number" value="0" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:6px;color:#c9d1d9" />
        </div>
        <button onclick="providersAddKey()" style="margin-top:10px;background:#238636;color:white;border:none;padding:8px 16px;border-radius:4px;cursor:pointer">Add key</button>
      </div>`;

    const fmtBalance = (k) => {
      const b = k.balance || {};
      if (!b || (!b.ok && !b.monthly_spend_usd)) {
        if (b && b.error) return `<span style="color:#f85149" title="${b.error.replace(/"/g,'&quot;')}">balance: error</span>`;
        return `<span style="color:#8b949e">balance: ?</span>`;
      }
      const ms = b.monthly_spend_usd || {};
      const usage = (typeof ms.usage === 'number') ? ms.usage.toFixed(2) : '?';
      const limit = (typeof ms.limit === 'number') ? ms.limit.toFixed(0) : '?';
      const remaining = (typeof ms.remaining === 'number') ? ms.remaining.toFixed(2) : '?';
      const pct = (ms.usage && ms.limit) ? Math.round((ms.usage / ms.limit) * 100) : 0;
      const colour = pct > 80 ? '#f85149' : (pct > 50 ? '#d29922' : '#3fb950');
      return `<span style="color:${colour}">$${usage}/${limit}</span><span style="color:#8b949e"> (left: $${remaining})</span>`;
    };

    const keysCard = keys.length === 0
      ? '<div class="card"><h3>No keys yet</h3><p>Add at least one above. Without keys, core can\'t run thinking.</p></div>'
      : `<div class="card"><h3>Keys (${keys.length})</h3>
          <button onclick="providersRefreshAll()" style="background:#1f6feb;color:white;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-size:12px;margin-bottom:10px">↻ Refresh all balances</button>
          ${keys.map(k => `
            <div class="event" style="border-left-color:${statusColor[k.status] || '#30363d'};margin-bottom:10px">
              <div class="meta">${k.provider} • ${k.name} • ${k.key_masked} • created ${k.created_at.slice(0,16)}</div>
              <div class="body" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px">
                ${statusBadge(k.status)}
                ${k.provider === 'fireworks' ? fmtBalance(k) : ''}
                <span>req=${k.request_count} ok=${k.success_count} err=${k.error_count}</span>
                ${k.last_used_at ? `<span style="color:#8b949e">last_used=${k.last_used_at.slice(0,19)}</span>` : ''}
                ${k.last_error ? `<span style="color:#f85149" title="${k.last_error.replace(/"/g,'&quot;')}">err: ${k.last_error.slice(0,60)}</span>` : ''}
              </div>
              <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">
                <button onclick="providersTestKey('${k.key_id}')" style="background:#1f6feb;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:11px">Test</button>
                ${k.provider === 'fireworks' ? `<button onclick="providersRefreshOne('${k.key_id}')" style="background:#30363d;color:#c9d1d9;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:11px">↻ Balance</button>` : ''}
                ${k.status !== 'active' ? `<button onclick="providersSetStatus('${k.key_id}','active')" style="background:#238636;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:11px">Activate</button>` : ''}
                ${k.status !== 'disabled' ? `<button onclick="providersSetStatus('${k.key_id}','disabled')" style="background:#6e7681;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:11px">Disable</button>` : ''}
                <button onclick="providersDeleteKey('${k.key_id}')" style="background:#da3633;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:11px">Delete</button>
              </div>
            </div>`).join('')}
        </div>`;

    return settingsCard + addCard + keysCard;
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
          <div class="meta">[${t.task_id}] ${t.created_by === 'ivan' ? '👤 Ivan' : '🤖 Sonya'} • ${t.notify_mode} • ${t.created_at.slice(0,19)}</div>
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
    alert(resp.ok ? JSON.stringify(data,null,2) : `Error ${resp.status}: ${JSON.stringify(data)}`);
    if (resp.ok) loadPage('providers');
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
