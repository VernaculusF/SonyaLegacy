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
    <div class="nav-item active" data-page="dashboard">⚡ Dashboard</div>
    <div class="nav-item" data-page="thoughts">💭 Thoughts</div>
    <div class="nav-item" data-page="memory">🧠 Memory</div>
    <div class="nav-item" data-page="telegram">📱 Telegram</div>
    <div class="nav-item" data-page="chat">💬 Chat</div>
    <div class="nav-item" data-page="audit">📋 Audit</div>
    <div class="nav-item" data-page="substrate">💾 Substrate</div>
    <div class="nav-item" data-page="core">⚙️ Core</div>
  </div>
  <div class="sidebar-footer">
    Sonya Environment v0.1<br>Packages: tg-bridge, tg-userbot
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

  try {
    const resp = await fetch(`${API}/api/${page}`);
    const data = await resp.json();
    content.innerHTML = renderers[page](data);
  } catch(e) {
    content.innerHTML = `<div class="card"><pre>Error: ${e.message}</pre></div>`;
  }
}

async function coreAction(action) {
  try {
    const resp = await fetch(`${API}/api/core/${action}`, {method: 'POST'});
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
      </div>
      <div class="card"><h3>Controls</h3>
        <button onclick="coreAction('start')" style="background:#238636;color:white;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;margin:5px;font-size:14px">▶ Start Core</button>
        <button onclick="coreAction('stop')" style="background:#da3633;color:white;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;margin:5px;font-size:14px">⬛ Stop Core</button>
        <button onclick="loadPage('core')" style="background:#30363d;color:#c9d1d9;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;margin:5px;font-size:14px">🔄 Refresh</button>
      </div>
      <div class="card"><h3>Logs (last 40 lines)</h3><pre id="core-logs" style="font-size:11px;max-height:400px;overflow-y:auto">${d.logs || 'No logs'}</pre></div>`;
  }
};

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
