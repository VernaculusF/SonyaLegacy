/* WebSocket client for /atrium/feed.
 *
 * Connects with X-Atrium-Token header (Phase 0 auth). Note: WebSocket spec
 * doesn't allow custom headers in browser — we pass token as query param
 * instead. The server should accept either.
 *
 * Reconnects with exponential backoff (1s, 2s, 4s, 8s, max 30s).
 *
 * See: docs/atrium/CHANNELS.md §3.
 */
import {
  feed, setFeed, settings,
  pushDialogMessage, pushStreamEvent, pushInnerThought,
  applyMeta, flashAvatar,
} from './store.js';

let ws = null;
let reconnectTimer = null;
let reconnectAttempt = 0;
let intentionalClose = false;

function classifySrc(kind, payload) {
  // Server already infers src in event JSON. Fall back to client-side
  // classification if missing.
  if (payload && payload.src) return payload.src;
  if (!kind) return 'system';
  // worker / task progress
  if (kind.startsWith('outgoing.worker_log') || kind.includes('task_worker')
      || kind.startsWith('task.')) return 'worker';
  // idle reflection
  if (kind.startsWith('internal.thought') || kind === 'internal.idle_thought') return 'idle';
  // dialog / outbound
  if (kind.startsWith('outgoing.dialog') || kind.startsWith('outgoing.telegram')
      || kind.startsWith('outgoing.response')) return 'active';
  if (kind.startsWith('outgoing.mind') || kind.startsWith('outgoing.body')
      || kind.startsWith('outgoing.voice')) return 'active';
  // active-session work: steps, session lifecycle, blockers, ticks, tool/shell
  if (kind.startsWith('internal.agent_step') || kind.startsWith('internal.agent_session')
      || kind.startsWith('internal.blocker') || kind.startsWith('internal.cognitive_tick')
      || kind.startsWith('internal.inbox') || kind.startsWith('internal.auto_ack')
      || kind.endsWith('_yolo') || kind.startsWith('shell.') || kind.startsWith('pip.')
      || kind.startsWith('code.') || kind.startsWith('web.') || kind.startsWith('filesystem.')) {
    return 'active';
  }
  // skills
  if (kind.startsWith('skill.') || kind.includes('capability_gap')) return 'skill';
  // selfmod
  if (kind.startsWith('self_mod') || kind.startsWith('selfmod')) return 'skill';
  // system: schedulers, lifecycle, initiative gating, nudges
  return 'system';
}

function isHisIncoming(kind) {
  return (
    kind?.startsWith('incoming.telegram_message') ||
    kind === 'incoming.atrium_dialog' ||
    kind === 'incoming.atrium_voice'
  );
}

function relativeAge(ts) {
  if (!ts) return '';
  try {
    const dt = new Date(ts);
    const ms = Date.now() - dt.getTime();
    if (ms < 60000) return Math.floor(ms / 1000) + 's';
    if (ms < 3600000) return Math.floor(ms / 60000) + 'm';
    if (ms < 86400000) return Math.floor(ms / 3600000) + 'h';
    return Math.floor(ms / 86400000) + 'd';
  } catch {
    return '';
  }
}

// Strip technical tags ("[workshop reply: …]", "[NEW MESSAGE]" etc.) and a
// trailing meta-line, so they don't leak into the chat bubble or TTS.
function cleanDialogText(t) {
  if (!t) return '';
  let s = String(t);
  // Drop leading bracket-tag lines: [workshop reply: ...]\n, [NEW MESSAGE], etc.
  s = s.replace(/^(?:\s*\[[^\]\n]{1,80}\][^\n]*\n)+/, '');
  // Drop standalone bracketed markers anywhere on their own line.
  s = s.replace(/^\s*\[[^\]\n]{1,80}\]\s*$/gm, '');
  // Collapse 3+ newlines.
  s = s.replace(/\n{3,}/g, '\n\n');
  return s.trim();
}

function handleEvent(msg) {
  const seq = msg.seq;
  const ts = msg.ts;
  const kind = msg.kind;
  const channel = msg.channel || '';
  const text = msg.text || '';
  const payload = msg.payload || {};
  const src = msg.src || classifySrc(kind, payload);

  if (seq && seq > feed.last_seq) {
    setFeed('last_seq', seq);
  }

  // Dialog messages (her replies in TG/Atrium)
  if (kind === 'outgoing.dialog' || kind === 'outgoing.telegram_initiative' || kind === 'outgoing.telegram_progress' || kind === 'outgoing.telegram_response' || kind === 'outgoing.response') {
    if (text) {
      const cleaned = cleanDialogText(text);
      if (cleaned) {
        const atts = Array.isArray(payload.attachments) ? payload.attachments : [];
        pushDialogMessage({ seq, ts, sender: 'her', text: cleaned, attachments: atts });
        // Only flash/notify for live events, not during the initial backlog
        // replay (otherwise a cold start spams the avatar + notifications).
        if (feed.synced) {
          flashAvatar();
        }
      }
    }
  }
  // Incoming from Ivan
  if (isHisIncoming(kind) && (text || (payload.attachments && payload.attachments.length) || payload.media_kind)) {
    const cleaned = cleanDialogText(text);
    const atts = Array.isArray(payload.attachments) ? payload.attachments : [];
    if (!atts.length && payload.media_kind) {
      atts.push({
        media_kind: payload.media_kind,
        media_mime: payload.media_mime,
        media_path: payload.media_path,
        name: payload.media_path ? String(payload.media_path).replace(/\\/g, '/').split('/').pop() : '',
      });
    }
    if (cleaned || atts.length) {
      pushDialogMessage({ seq, ts, sender: 'him', text: cleaned, attachments: atts });
    }
  }

  // Inner thought stream (mind.thought events)
  if (kind === 'outgoing.mind_thought' && text) {
    pushInnerThought({
      seq,
      ts,
      text,
      age: relativeAge(ts),
      private: !!payload.private,
    });
  }

  // mind.focus updates focus directly (in addition to meta sync)
  if (kind === 'outgoing.mind_focus' && text) {
    setFeed('current_focus', text);
  }

  // Reason-stream — all events except pure dialog noise
  // Skip pure-dialog kinds because they're already in Dialog pane
  const skipFromStream = new Set([
    'outgoing.telegram_initiative',
    'outgoing.telegram_progress',
    'outgoing.telegram_response',
    'outgoing.response',
  ]);

  // Typing indicator: while an active session is between scheduling and the
  // outgoing.* delivery, mark her_typing so the Atrium UI shows the typing
  // dots. A reset on her outgoing closes it.
  if (kind === 'internal.active_session_scheduled' || kind === 'internal.active_session_requested_external') {
    if (feed.synced) setFeed('her_typing', true);
  }
  if (kind === 'internal.agent_step' && payload && payload.tool === 'chat.dialog') {
    if (feed.synced) setFeed('her_typing', true);
  }
  if (kind && (kind.startsWith('outgoing.dialog') || kind.startsWith('outgoing.telegram_progress')
    || kind.startsWith('outgoing.telegram_initiative') || kind.startsWith('outgoing.telegram_response')
    || kind.startsWith('outgoing.response'))) {
    setFeed('her_typing', false);
  }
  if (kind === 'internal.agent_session_outcome') {
    setFeed('her_typing', false);
  }
  // Keep outgoing.dialog in stream so Иван sees it on the timeline too,
  // but with src=active so it's visually marked.
  if (!skipFromStream.has(kind)) {
    let body = '';
    if (kind === 'internal.thought' && payload.text) {
      body = `"${payload.text}"`;
    } else if (text) {
      body = text;
    } else if (payload.tool) {
      body = `tool=${payload.tool} ${payload.arg ? '· ' + String(payload.arg).slice(0, 100) : ''}`;
    } else if (payload.summary) {
      body = payload.summary;
    } else if (payload.next_step) {
      body = `next: ${payload.next_step}`;
    } else if (kind.startsWith('internal.scheduler')) {
      body = '';
    } else {
      // Fallback: short payload preview
      try {
        body = JSON.stringify(payload).slice(0, 150);
      } catch { body = ''; }
    }
    pushStreamEvent({
      seq,
      ts: ts ? new Date(ts).toLocaleTimeString('ru-RU', { hour12: false }) : '',
      kind,
      src,
      channel,
      session_id: msg.session_id,
      body,
    });
  }
}

function handleMeta(msg) {
  applyMeta(msg);
}

export function connectWS() {
  intentionalClose = false;
  if (!settings.vps_host || !settings.atrium_token) {
    setFeed({ connected: false, last_error: 'connection settings missing' });
    return;
  }
  // Reset sync state — suppress side-effects until this connection's backlog
  // catch-up completes (server sends a 'synced' sentinel).
  setFeed({ reconnecting: true, last_error: '', synced: false });

  // ws:// for plain http hosts; wss:// will be handled when we add TLS later.
  const proto = settings.vps_host.startsWith('localhost') ? 'ws' : 'ws';
  // Cold start (last_seq=0): ask the server for a small recent tail only
  // (backlog clamp) so we don't replay the entire history. On reconnect
  // (last_seq>0) resume exactly from where we left off.
  const sinceParam = `since_seq=${feed.last_seq}`;
  const backlogParam = feed.last_seq > 0 ? '' : '&backlog=150';
  const url = `${proto}://${settings.vps_host}/atrium/feed?${sinceParam}${backlogParam}&token=${encodeURIComponent(settings.atrium_token)}`;

  try {
    // Browser WebSocket can't set custom headers; the server reads token from
    // the X-Atrium-Token header by default but we also accept ?token=... for
    // browser-based clients. Backend update may be needed (T1.4).
    ws = new WebSocket(url);
  } catch (err) {
    setFeed({ connected: false, last_error: String(err) });
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    reconnectAttempt = 0;
    setFeed({ connected: true, reconnecting: false, last_error: '' });
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'event') {
        handleEvent(msg);
      } else if (msg.type === 'meta') {
        handleMeta(msg);
      } else if (msg.type === 'synced') {
        // Backlog catch-up done — live events follow. Enable side-effects.
        if (msg.last_seq && msg.last_seq > feed.last_seq) {
          setFeed('last_seq', msg.last_seq);
        }
        setFeed('synced', true);
      }
    } catch (err) {
      console.error('atrium ws parse error', err);
    }
  };

  ws.onerror = () => {
    // onclose will fire too, handle reconnect there.
  };

  ws.onclose = (ev) => {
    setFeed({ connected: false });
    if (!intentionalClose) {
      scheduleReconnect();
    }
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectAttempt = Math.min(reconnectAttempt + 1, 5);
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempt - 1), 30000);
  setFeed({ reconnecting: true });
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWS();
  }, delay);
}

export function disconnectWS() {
  intentionalClose = true;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    try {
      ws.close();
    } catch {}
    ws = null;
  }
  setFeed({ connected: false, reconnecting: false });
}

// HTTP nudge endpoint — reply from reason-stream pane.
export async function sendNudge({ session_id, text, ref_seq }) {
  if (!settings.vps_host || !settings.atrium_token) {
    throw new Error('connection settings missing');
  }
  const url = `http://${settings.vps_host}/api/atrium/nudge`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Atrium-Token': settings.atrium_token,
    },
    body: JSON.stringify({ session_id, text, ref_seq }),
  });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${txt}`);
  }
  return resp.json();
}

// HTTP dialog endpoint (T1.4) — Ivan types in the composer. Records an
// incoming dialog turn + triggers an active session so she replies.
// `attachments` is an optional array of upload refs from uploadAtriumFile().
export async function sendDialog(text, attachments = []) {
  if (!settings.vps_host || !settings.atrium_token) {
    throw new Error('connection settings missing');
  }
  const url = `http://${settings.vps_host}/api/atrium/dialog`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Atrium-Token': settings.atrium_token,
    },
    body: JSON.stringify({ text, attachments }),
  });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${txt}`);
  }
  return resp.json();
}

// Upload a file attachment to the Atrium media store. Returns the upload ref
// {name, media_path, media_mime, media_kind, url, size} to pass into sendDialog.
export async function uploadAtriumFile(file, onProgress) {
  if (!settings.vps_host || !settings.atrium_token) {
    throw new Error('connection settings missing');
  }
  const url = `http://${settings.vps_host}/api/atrium/upload`;
  const form = new FormData();
  form.append('file', file, file.name);
  // Use XMLHttpRequest for upload progress events.
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.setRequestHeader('X-Atrium-Token', settings.atrium_token);
    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }
    xhr.onload = () => {
      let json;
      try { json = JSON.parse(xhr.responseText); } catch { json = { error: xhr.responseText }; }
      if (xhr.status >= 200 && xhr.status < 300 && json.ok) resolve(json);
      else reject(new Error(json.error || `HTTP ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error('upload failed (network)'));
    xhr.send(form);
  });
}

// Absolute URL for a media file served by the admin server.
export function mediaUrl(nameOrPath) {
  if (!nameOrPath) return '';
  // Accept either a bare name or a full server path — extract the basename.
  const name = String(nameOrPath).replace(/\\/g, '/').split('/').pop();
  const tok = encodeURIComponent(settings.atrium_token || '');
  return `http://${settings.vps_host}/api/atrium/media/${encodeURIComponent(name)}?token=${tok}`;
}

// HTTP heartbeat (T1.5) — keep-alive so the backend knows Atrium is the live
// primary surface (affects TG emergency-fallback). Fire-and-forget.
export async function sendHeartbeat() {
  if (!settings.vps_host || !settings.atrium_token) return;
  try {
    await fetch(`http://${settings.vps_host}/api/atrium/heartbeat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Atrium-Token': settings.atrium_token,
      },
      body: '{}',
    });
  } catch {
    // non-fatal — WS feed also marks heartbeat
  }
}

let _heartbeatTimer = null;

export function startHeartbeat(intervalMs = 60000) {
  stopHeartbeat();
  sendHeartbeat();
  _heartbeatTimer = setInterval(sendHeartbeat, intervalMs);
}

export function stopHeartbeat() {
  if (_heartbeatTimer) {
    clearInterval(_heartbeatTimer);
    _heartbeatTimer = null;
  }
}
