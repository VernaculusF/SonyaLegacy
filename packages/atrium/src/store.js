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
  vps_host: '34.38.255.149:8877',
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
  // Avatar VRM model URL. Default served from public/models by Vite/Tauri.
  // Empty → fall back to the static SVG silhouette.
  avatar_model_url: '/models/sonya.vrm',
  // Optional GLB/glTF room scene for the room view. Empty → procedural room.
  room_model_url: '',
  // Avatar render mode: '2d' (PNGtuber-style, default — clean, no rig) | '3d' (VRM).
  avatar_mode: '2d',
  // Optional 2D mouth frames (image URLs) ordered closed → open. Empty → drawn SVG head.
  // 4 AI-generated 2B frames: closed → half → open → wide.
  avatar_frames: [
    '/avatar/sonya_closed.png',
    '/avatar/sonya_half.png',
    '/avatar/sonya_open.png',
    '/avatar/sonya_wide.png',
  ],
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
    };
    // Backfill avatar_frames from default if an old save had it empty/missing
    // (so existing users get the new generated frames without re-onboarding).
    if (!Array.isArray(merged.avatar_frames) || merged.avatar_frames.length === 0) {
      merged.avatar_frames = [...DEFAULT_SETTINGS.avatar_frames];
    }
    if (!merged.avatar_mode) merged.avatar_mode = DEFAULT_SETTINGS.avatar_mode;
    return merged;
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

function saveSettings(s) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    // localStorage might be disabled / full — non-fatal
  }
}

export const [settings, setSettings] = createStore(loadSettings());

export function updateSetting(key, value) {
  setSettings(key, value);
  saveSettings(settings);
}

export function updateFilter(src, on) {
  setSettings('streams_filters', src, on);
  saveSettings(settings);
}

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
});

// Cap collections to avoid unbounded growth
const MAX_STREAM = 500;
const MAX_DIALOG = 200;
const MAX_THOUGHTS = 50;

export function pushDialogMessage(msg) {
  setFeed('dialog_messages', (cur) => {
    // Dedup by seq — reconnects / overlapping catch-up must not double-post.
    if (msg.seq != null && cur.some((m) => m.seq === msg.seq)) return cur;
    const next = [...cur, msg];
    if (next.length > MAX_DIALOG) next.splice(0, next.length - MAX_DIALOG);
    return next;
  });
}

export function pushStreamEvent(ev) {
  setFeed('stream_events', (cur) => {
    if (ev.seq != null && cur.some((e) => e.seq === ev.seq)) return cur;
    const next = [...cur, ev];
    if (next.length > MAX_STREAM) next.splice(0, next.length - MAX_STREAM);
    return next;
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

// Speaking state — drives 2D mouth animation. setSpeaking(true) starts a
// talk loop; mouthLevel (0..1) is the live amplitude when real TTS lands.
export const [speaking, setSpeaking] = createSignal(false);
export const [mouthLevel, setMouthLevel] = createSignal(0);

let _speakTimer = null;
// Simulate talking for `ms` (used until real TTS amplitude is wired): toggles
// the mouth open/closed at a natural cadence, then settles closed.
export function simulateSpeech(ms = 2500) {
  setSpeaking(true);
  if (_speakTimer) clearInterval(_speakTimer);
  const start = Date.now();
  _speakTimer = setInterval(() => {
    if (Date.now() - start > ms) {
      clearInterval(_speakTimer);
      _speakTimer = null;
      setMouthLevel(0);
      setSpeaking(false);
      return;
    }
    // pseudo-random mouth openness for a lively talk cadence
    setMouthLevel(0.2 + Math.random() * 0.8);
  }, 90);
}
