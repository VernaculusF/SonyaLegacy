/* Atrium global state via Solid stores.
 *
 * Two stores:
 *  - settings: connection config + UI prefs, persisted in localStorage
 *  - feed: live state from WS — events, dialog, mind, drives, env
 *
 * См. docs/atrium/CHANNELS.md §3 для protocol.
 */
import { createStore } from 'solid-js/store';
import { createSignal } from 'solid-js';

// ---------- Settings (persisted) ----------

const SETTINGS_KEY = 'atrium.settings.v1';

const DEFAULT_SETTINGS = {
  vps_host: typeof window !== 'undefined'
    ? window.location.host
    : 'localhost:8877',
  atrium_token: '',
  // UI prefs
  streams_collapsed: false,
  streams_filters: {
    active: true,
    worker: true,
    idle: true,
    skill: true,
    system: false, // muted by default
  },
  show_private_count: true,
  notifications_dialog: 'full', // full | quiet | off
  notifications_stuck: true,
  // Workspace runtime settings — чаты как контексты диалога
  workspaces: [
    { id: 'main', name: 'main', description: 'Основной чат — общие вопросы, задачи, наблюдение за проектами', path: '', type: 'local', created_at: Date.now(), last_message_at: Date.now() },
  ],
  full_system_access: false, // Full-System Access toggle
  // Avatar VRM model URL. Default served from public/models by Vite/Tauri.
  // Empty → fall back to the static SVG silhouette.
  avatar_model_url: '/models/sonya.vrm',
  // Optional GLB/glTF room scene for the room view. Empty → procedural room.
  room_model_url: '',
  // Avatar render mode: '2d' (PNGtuber-style, default — clean, no rig) | '3d' (VRM).
  avatar_mode: '2d',
  // Optional 2D mouth frames (image URLs) ordered closed → open. Empty → drawn SVG head.
  // 4 AI-generated 2B frames (Ivan's, фон вырезан, 1600×2400 RGBA, выровнены).
  // closed → half → open → wide. wide (последний) — ОЧЕНЬ редкий (только пики).
  avatar_frames: [
    '/avatar/sonya_closed.png',
    '/avatar/sonya_half.png',
    '/avatar/sonya_open.png',
    '/avatar/sonya_wide.png',
  ],
  // Emotion sprites: marker → image URL. Shown when an expression is set and
  // she's idle (not talking). Talking falls back to avatar_frames so the mouth
  // still animates. Files live in public/avatar/emotions/.
  avatar_emotions: {
    desire: '/avatar/emotions/desire.png',
    desire_bite: '/avatar/emotions/desire_bite.png',
    sad: '/avatar/emotions/sad.png',
    sad_tears: '/avatar/emotions/sad_tears.png',
    angry: '/avatar/emotions/angry.png',
    shy: '/avatar/emotions/shy.png',
    joy: '/avatar/emotions/joy.png',
    tender: '/avatar/emotions/tender.png',
    surprised: '/avatar/emotions/surprised.png',
    thinking: '/avatar/emotions/thinking.png',
    playful: '/avatar/emotions/playful.png',
    calm: '/avatar/emotions/calm.png',
  },
};

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    const parsed = JSON.parse(raw);
    // Merge with defaults so new keys don't break old saves
    const merged = {
      ...DEFAULT_SETTINGS,
      ...parsed,
      streams_filters: {
        ...DEFAULT_SETTINGS.streams_filters,
        ...(parsed.streams_filters || {}),
      },
      workspaces: (() => {
        // Migration: take saved workspaces if any, ensuring main is present
        let ws = Array.isArray(parsed.workspaces) && parsed.workspaces.length > 0
          ? parsed.workspaces.map(w => {
              // Strip old `active` field from pre-drawer format
              const { active, ...rest } = w;
              return rest;
            })
          : DEFAULT_SETTINGS.workspaces;
        // Ensure main workspace always exists as first entry
        if (!ws.some(w => w.id === 'main')) {
          ws = [...DEFAULT_SETTINGS.workspaces, ...ws];
        }
        return ws;
      })(),
      full_system_access: Boolean(parsed.full_system_access),
    };
    // Backfill / refresh avatar_frames. Empty → use default. Also refresh when
    // the saved frames point at the bundled /avatar/sonya_ assets (so a version
    // change of the bundled frames — e.g. .png→.jpg — takes effect without
    // re-onboarding). Custom user paths (not /avatar/sonya_) are preserved.
    const isBundled = Array.isArray(merged.avatar_frames)
      && merged.avatar_frames.every((u) => typeof u === 'string' && u.startsWith('/avatar/sonya_'));
    if (!Array.isArray(merged.avatar_frames) || merged.avatar_frames.length === 0 || isBundled) {
      merged.avatar_frames = [...DEFAULT_SETTINGS.avatar_frames];
    }
    // Always refresh bundled emotion map from default (new emotions ship over
    // time; user has no custom emotion config UI yet).
    merged.avatar_emotions = { ...DEFAULT_SETTINGS.avatar_emotions, ...(parsed.avatar_emotions || {}) };
    if (!merged.avatar_mode) merged.avatar_mode = DEFAULT_SETTINGS.avatar_mode;
    return merged;
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export const [settings, setSettings] = createStore(loadSettings());

export function saveSettings(s) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    // localStorage might be disabled / full — non-fatal
  }
}

export function updateSetting(key, value) {
  setSettings(key, value);
  saveSettings(settings);
}

export function updateFilter(src, on) {
  setSettings('streams_filters', src, on);
  saveSettings(settings);
}

// ---------- Workspace / Chat functions ----------

// Текущий активный чат (один, не мультивыбор)
export const [activeWorkspaceId, setActiveWorkspaceId] = createSignal('main');

export function switchWorkspace(id) {
  setActiveWorkspaceId(id);
}

export function createWorkspace(ws) {
  setSettings('workspaces', (cur) => {
    if (cur.some((w) => w.id === ws.id)) return cur;
    return [...cur, {
      ...ws,
      created_at: ws.created_at || Date.now(),
      last_message_at: ws.last_message_at || Date.now(),
    }];
  });
  saveSettings(settings);
  setActiveWorkspaceId(ws.id);
}

export function removeWorkspace(id) {
  if (id === 'main') return; // нельзя удалить основной чат
  setSettings('workspaces', (cur) => cur.filter((w) => w.id !== id));
  saveSettings(settings);
  if (activeWorkspaceId() === id) setActiveWorkspaceId('main');
}

export function updateWorkspace(id, updates) {
  setSettings('workspaces', (cur) =>
    cur.map((w) => (w.id === id ? { ...w, ...updates } : w))
  );
  saveSettings(settings);
}

export function touchWorkspace(id) {
  setSettings('workspaces', (cur) =>
    cur.map((w) => (w.id === id ? { ...w, last_message_at: Date.now() } : w))
  );
  saveSettings(settings);
}

export function getWorkspace(id) {
  return settings.workspaces.find((w) => w.id === id) || null;
}

/**
 * Windows-native folder picker (showDirectoryPicker).
 * Returns the picked folder path as string, or null if cancelled / unavailable.
 * Falls back to a prompt() if the API isn't supported.
 */
export async function pickProjectFolder() {
  try {
    if (typeof window !== 'undefined' && window.showDirectoryPicker) {
      const handle = await window.showDirectoryPicker({ mode: 'readwrite' });
      // Browser file-system APIs intentionally hide the absolute path.
      // We still use the native picker for convenience, then ask the user to
      // confirm the real path explicitly so project bindings stay stable.
      const hinted = prompt(
        `Выбрана папка "${handle.name}". Введите полный путь к проекту:`,
        handle.name,
      );
      return hinted ? { path: hinted, handle } : null;
    }
  } catch (e) {
    if (e.name === 'AbortError') return null; // user cancelled
    // fall through to prompt
  }
  // Fallback for non-Chrome browsers
  const path = prompt('Введите путь к папке проекта (например C:\\Projects\\sonya-core):');
  return path ? { path, handle: null } : null;
}

// Алиас для совместимости — addWorkspace = createWorkspace
export const addWorkspace = createWorkspace;

// ---------- Live feed state ----------

export const [feed, setFeed] = createStore({
  // Connection
  connected: false,
  reconnecting: false,
  last_error: '',
  last_seq: 0,
  // Dialog (filtered to channel=dialog)
  dialog_messages: [], // {seq, ts, sender: 'her'|'him', text}
  // Reason-stream (everything else worth showing)
  stream_events: [], // {seq, ts, kind, src, channel, body, payload}
  // Mind state (from meta)
  current_focus: '',
  current_outfit: 'home',
  current_expression: 'neutral',
  mood_tint: 'neutral',
  drives: {
    boredom: 0,
    curiosity: 0,
    relational_focus: 0,
    pending_debt: 0,
  },
  private_count_last_hour: 0,
  // Inner stream (mind.thought events with timestamps)
  inner_thoughts: [], // {seq, ts, text}
  // Activity hint
  her_typing: false,
  // True once the initial backlog catch-up is done (server 'synced' sentinel).
  // While false, side-effects (avatar glow, notifications) are suppressed so
  // the cold-start replay doesn't spam.
  synced: false,
  // Projects — fetched from /api/projects
  projects: [],
  // Evolution pressure dimensions — fetched from /api/evolution-pressure
  evolution_pressure: [],
});

// Cap collections to avoid unbounded growth
const MAX_STREAM = 500;
const MAX_DIALOG = 200;
const MAX_THOUGHTS = 50;

export function pushDialogMessage(msg) {
  // If caller explicitly set workspace_id, use it. Otherwise the message
  // belongs to the global (main) dialog. Only non-main workspaces require
  // tagging so per-project chat filtering works.
  const tagged = msg.workspace_id ? msg : { ...msg, workspace_id: undefined };
  setFeed('dialog_messages', (cur) => {
    // Dedup by seq — reconnects / overlapping catch-up must not double-post.
    if (tagged.seq != null && cur.some((m) => m.seq === tagged.seq)) return cur;
    // Dedup optimistic echo vs WS echo: same sender + same text within 30s.
    // The composer pushes a local- echo immediately; the backend later emits
    // the same text with a real seq via the feed. We must NOT remove+re-add
    // (that causes a visible flicker) — instead we keep the existing bubble
    // in place and just upgrade its seq in-place if it was a local echo.
    if (tagged.text) {
      const t = tagged.ts ? new Date(tagged.ts).getTime() : Date.now();
      const dupIdx = cur.findIndex((m) =>
        m.sender === tagged.sender &&
        (m.text || '').trim() === (tagged.text || '').trim() &&
        Math.abs((m.ts ? new Date(m.ts).getTime() : 0) - t) < 30000
      );
      if (dupIdx >= 0) {
        const existing = cur[dupIdx];
        // Upgrade local echo → real seq without changing array order/length.
        if (typeof tagged.seq === 'number' && String(existing.seq).startsWith('local-')) {
          const copy = cur.slice();
          copy[dupIdx] = { ...existing, seq: tagged.seq, ts: existing.ts };
          return copy;
        }
        // Otherwise it's a true duplicate — ignore.
        return cur;
      }
    }
    const next = [...cur, tagged];
    if (next.length > MAX_DIALOG) next.splice(0, next.length - MAX_DIALOG);
    return next;
  });
  touchWorkspace(tagged.workspace_id || 'main');
}

export function pushStreamEvent(ev) {
  setFeed('stream_events', (cur) => {
    if (ev.seq != null && cur.some((e) => e.seq === ev.seq)) return cur;
    const next = [...cur, ev];
    if (next.length > MAX_STREAM) next.splice(0, next.length - MAX_STREAM);
    return next;
  });
}

// Prepend older dialog messages (history pagination). Dedupes by seq.
export function prependDialogMessages(msgs) {
  if (!Array.isArray(msgs) || !msgs.length) return;
  setFeed('dialog_messages', (cur) => {
    const seen = new Set(cur.map((m) => m.seq));
    const fresh = msgs.filter((m) => !seen.has(m.seq));
    if (!fresh.length) return cur;
    return [...fresh, ...cur];
  });
}

export function pushInnerThought(t) {
  setFeed('inner_thoughts', (cur) => {
    if (t.seq != null && cur.some((x) => x.seq === t.seq)) return cur;
    const next = [t, ...cur]; // latest first
    if (next.length > MAX_THOUGHTS) next.length = MAX_THOUGHTS;
    return next;
  });
}

export function applyMeta(meta) {
  setFeed({
    private_count_last_hour: meta.private_count_last_hour ?? 0,
    current_focus: meta.current?.current_focus ?? feed.current_focus,
    current_outfit: meta.current?.current_outfit ?? feed.current_outfit,
    current_expression: meta.current?.current_expression ?? feed.current_expression,
    mood_tint: meta.current?.mood_tint ?? feed.mood_tint,
    drives: { ...feed.drives, ...(meta.drives || {}) },
  });
}

// Avatar glow signal — pulses when she sends a dialog message
export const [avatarGlow, setAvatarGlow] = createSignal(0);

export function flashAvatar() {
  setAvatarGlow((n) => n + 1);
}

// ---------- Execution trace (in-memory, from WS feed) ----------
const MAX_TRACE = 200;
export const [executionTrace, setExecutionTrace] = createStore({ events: [] });

export function addTraceEvent(ev) {
  const event = { ...ev, ts: ev.ts || Date.now() };
  setExecutionTrace('events', (cur) => {
    const next = [...cur, event];
    if (next.length > MAX_TRACE) next.splice(0, next.length - MAX_TRACE);
    return next;
  });
}

export function clearTrace(phase) {
  if (phase) setExecutionTrace('events', (cur) => cur.filter((e) => e.phase !== phase));
  else setExecutionTrace('events', []);
}

export function getTrace(phase, limit = 50) {
  const all = executionTrace.events;
  const filtered = phase ? all.filter((e) => e.phase === phase) : all;
  return filtered.slice(-limit);
}

// Speaking state — drives 2D mouth animation. setSpeaking(true) starts a
// talk loop; mouthLevel (0..1) is the live amplitude when real TTS lands.
export const [speaking, setSpeaking] = createSignal(false);
export const [mouthLevel, setMouthLevel] = createSignal(0);

let _speakRaf = null;
let _speakEnd = 0;

// Simulate natural talking until `ms` elapses. Instead of constant random
// jitter, we model speech as syllable pulses: the mouth opens to a target,
// then relaxes, with brief between-word closes — reads like a talking gif.
// Replaced 1:1 by real TTS amplitude later (call setMouthLevel from audio).
export function simulateSpeech(ms = 2500) {
  setSpeaking(true);
  _speakEnd = performance.now() + ms;
  if (_speakRaf) return; // loop already running; just extended _speakEnd

  // Word/syllable envelope: words are bursts of 2-5 syllables, with clear
  // silences (mouth fully closed) BETWEEN words — that's what reads as speech.
  let target = 0;
  let nextChangeAt = 0;
  let sylLeft = 0;       // syllables remaining in the current word
  let lastEmit = 0;

  const loop = (now) => {
    if (now >= _speakEnd) {
      setMouthLevel(0);
      setSpeaking(false);
      cancelAnimationFrame(_speakRaf);
      _speakRaf = null;
      return;
    }
    _speakRaf = requestAnimationFrame(loop);

    if (now >= nextChangeAt) {
      if (sylLeft <= 0) {
        // between-word silence — mouth closes fully
        target = 0;
        sylLeft = 2 + Math.floor(Math.random() * 4); // next word: 2-5 syllables
        nextChangeAt = now + 130 + Math.random() * 170; // pause length
      } else {
        // a syllable: mostly quiet/normal, RARE loud peak (frame 3 only on
        // emphatic beats — Ivan asked frame 4 be ОЧЕНЬ редкое).
        const r = Math.random();
        target = r < 0.04 ? 0.92 + Math.random() * 0.08    // wide (very rare)
               : r < 0.55 ? 0.34 + Math.random() * 0.3     // normal (frame 2)
               :            0.10 + Math.random() * 0.14;   // quiet (frame 1)
        sylLeft -= 1;
        nextChangeAt = now + 95 + Math.random() * 85;     // ~5-7 syll/sec
      }
    }
    const cur = mouthLevel();
    const k = target > cur ? 0.5 : 0.3; // snappy open, softer close
    const next = cur + (target - cur) * k;
    if (now - lastEmit >= 33) { // ~30fps reactive writes
      lastEmit = now;
      setMouthLevel(next < 0.01 ? 0 : next);
    }
  };
  _speakRaf = requestAnimationFrame(loop);
}

// Real TTS hook (Этап 2): feed live amplitude 0..1 each audio frame.
export function setLiveMouth(level) {
  setSpeaking(true);
  setMouthLevel(Math.max(0, Math.min(1, level)));
}
export function endSpeech() {
  _speakEnd = 0;
  setMouthLevel(0);
  setSpeaking(false);
}

// ---- Project API fetch helpers ----

function _apiBase() {
  const host = settings.vps_host || (typeof window !== 'undefined' ? window.location.host : 'localhost:8877');
  const proto = (typeof location !== 'undefined' && location.protocol === 'https:') ? 'https' : 'http';
  return proto + '://' + host;
}

function _apiHeaders(extra) {
  return { 'X-Atrium-Token': settings.atrium_token || '', 'Content-Type': 'application/json', ...extra };
}

export async function fetchProjects() {
  try {
    const res = await fetch(_apiBase() + '/api/projects', { headers: _apiHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    setFeed('projects', data.projects || []);
  } catch { /* ignore */ }
}

export async function deleteProject(projectId) {
  try {
    const res = await fetch(_apiBase() + '/api/projects/' + projectId, {
      method: 'DELETE',
      headers: _apiHeaders(),
    });
    if (!res.ok) return false;
    await fetchProjects();
    return true;
  } catch { return false; }
}

export async function updateProjectStatus(projectId, status) {
  try {
    const res = await fetch(_apiBase() + '/api/projects/' + projectId, {
      method: 'POST',
      headers: _apiHeaders(),
      body: JSON.stringify({ status }),
    });
    if (!res.ok) return false;
    await fetchProjects();
    return true;
  } catch { return false; }
}

export async function fetchEvolutionPressure() {
  try {
    const res = await fetch(_apiBase() + '/api/evolution-pressure', { headers: _apiHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    setFeed('evolution_pressure', data.dimensions || []);
  } catch { /* ignore */ }
}

export async function fetchProjectTraces(projectId) {
  try {
    const res = await fetch(_apiBase() + '/api/projects/' + projectId + '/traces', { headers: _apiHeaders() });
    if (!res.ok) return [];
    const data = await res.json();
    return data.traces || [];
  } catch { return []; }
}

export async function fetchProjectRuns(projectId) {
  try {
    const res = await fetch(_apiBase() + '/api/projects/' + projectId + '/runs', { headers: _apiHeaders() });
    if (!res.ok) return [];
    const data = await res.json();
    return data.runs || [];
  } catch { return []; }
}

export async function cancelProjectRun(projectId, runId) {
  try {
    const res = await fetch(_apiBase() + '/api/projects/' + projectId + '/runs/' + runId + '/cancel', {
      method: 'POST',
      headers: _apiHeaders(),
    });
    return res.ok;
  } catch { return false; }
}

export async function controlProjectRun(projectId, runId, action) {
  if (!['pause', 'resume', 'approve', 'deny'].includes(action)) return false;
  try {
    const res = await fetch(_apiBase() + '/api/projects/' + projectId + '/runs/' + runId + '/' + action, {
      method: 'POST',
      headers: _apiHeaders(),
    });
    return res.ok;
  } catch { return false; }
}

export async function createProject(title, description, workspacePath) {
  try {
    const res = await fetch(_apiBase() + '/api/projects', {
      method: 'POST',
      headers: _apiHeaders(),
      body: JSON.stringify({ title, description, workspace_path: workspacePath }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    await fetchProjects();
    return data;
  } catch { return null; }
}

export async function setWorkspacePolicy(workspaceId, policy) {
  try {
    const res = await fetch(_apiBase() + '/api/workspace-policy/' + workspaceId, {
      method: 'POST',
      headers: _apiHeaders(),
      body: JSON.stringify(policy),
    });
    return res.ok;
  } catch { return false; }
}
