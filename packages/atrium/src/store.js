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
  // Voice playback: 'off' (default until user enables) | 'browser' (free OS
  // TTS, ru-RU) | 'local' (local Silero v4_ru, services/tts/server.py) |
  // 'cloned' (XTTS-v2 cloned voice — позже, тот же local сервис).
  voice_mode: 'off',
  // Local TTS service URL (used when voice_mode='local'|'cloned').
  tts_url: 'http://127.0.0.1:8878',
  // Voice id for local TTS. Silero v4_ru: baya|aidar|kseniya|xenia|eugene.
  tts_voice: 'baya',
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
    // Dedup optimistic echo vs WS echo: same sender + same text within 8s.
    // (composer pushes a local- echo; the backend later emits the same text
    // with a real seq — without this they'd both show.)
    if (msg.text) {
      const t = msg.ts ? new Date(msg.ts).getTime() : Date.now();
      const dup = cur.some((m) =>
        m.sender === msg.sender &&
        (m.text || '').trim() === (msg.text || '').trim() &&
        Math.abs((m.ts ? new Date(m.ts).getTime() : 0) - t) < 8000
      );
      if (dup) {
        // Prefer the real-seq copy: if incoming has a numeric seq and the
        // existing one was a local echo, replace it so reply/scroll keys are stable.
        if (typeof msg.seq === 'number') {
          return cur.map((m) =>
            (m.sender === msg.sender && (m.text || '').trim() === (msg.text || '').trim()
              && String(m.seq).startsWith('local-')) ? { ...msg } : m
          );
        }
        return cur;
      }
    }
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
        // a syllable: mostly quiet/normal, occasional louder peak
        const r = Math.random();
        target = r < 0.15 ? 0.78 + Math.random() * 0.22   // loud (rare → frame 3)
               : r < 0.6  ? 0.34 + Math.random() * 0.3    // normal (frame 2)
               :            0.12 + Math.random() * 0.16;  // quiet (frame 1)
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
