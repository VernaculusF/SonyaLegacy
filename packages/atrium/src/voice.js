/* voice.js — text-to-speech playback for Atrium.
 *
 * Backends, selected via settings.voice_mode:
 *   - 'off'         — no speech.
 *   - 'browser'     — Web Speech API (free OS TTS, mediocre RU). Fallback.
 *   - 'local'       — local Piper TTS service (services/tts, 127.0.0.1:8878).
 *                     Free, neural, real-time on CPU. Mid quality (Irina).
 *   - 'elevenlabs'  — ElevenLabs proxy via VPS admin server. Best quality,
 *                     любой voice из voice library, но платно (free tier 10K
 *                     symbols/mo). API key хранится только на VPS.
 *
 * All backends feed the same mouthLevel/speaking signals via Web Audio
 * AnalyserNode (mouthAudio.attachAudioEl) so lip-sync is identical.
 */
import { settings, setSpeaking, setMouthLevel, mouthLevel } from './store.js';
import { attachAudioEl, stopMouthAudio } from './mouthAudio.js';

// ---------- Browser (Web Speech) backend ----------
let _ruVoice = null;
let _voicesPolled = false;

function pickRuVoice() {
  if (typeof speechSynthesis === 'undefined') return null;
  const all = speechSynthesis.getVoices();
  if (!all.length) return null;
  const preferRu = all.filter((v) => /^ru/i.test(v.lang));
  const femaleNames = /irina|tatyana|katya|svetlana|daria|milena|natasha|ekaterina|alena|alyona|ksenia/i;
  _ruVoice =
    preferRu.find((v) => femaleNames.test(v.name)) ||
    preferRu[0] ||
    all[0];
  _voicesPolled = true;
  return _ruVoice;
}

if (typeof speechSynthesis !== 'undefined') {
  speechSynthesis.addEventListener('voiceschanged', pickRuVoice);
  pickRuVoice();
}

// ---------- common state ----------
let _mouthRaf = null;
let _audioEl = null;        // local backend playback element
let _audioObjectUrl = null; // revoke after end

function _stopMouthLoop() {
  if (_mouthRaf) cancelAnimationFrame(_mouthRaf);
  _mouthRaf = null;
  setMouthLevel(0);
  setSpeaking(false);
}

function _stopAudio() {
  if (_audioEl) {
    try { _audioEl.pause(); } catch {}
    try { _audioEl.src = ''; } catch {}
    _audioEl = null;
  }
  if (_audioObjectUrl) {
    try { URL.revokeObjectURL(_audioObjectUrl); } catch {}
    _audioObjectUrl = null;
  }
  stopMouthAudio();
}

export function isVoiceOn() {
  return settings.voice_mode && settings.voice_mode !== 'off';
}

export function stopVoice() {
  if (typeof speechSynthesis !== 'undefined') {
    try { speechSynthesis.cancel(); } catch {}
  }
  _stopAudio();
  _stopMouthLoop();
}

// ---------- Backend: browser TTS ----------
function _speakBrowser(text, opts) {
  if (!('speechSynthesis' in window)) return false;
  if (!_voicesPolled) pickRuVoice();
  speechSynthesis.cancel();
  _stopMouthLoop();

  const chunks = _splitForTTS(text, 220);
  if (!chunks.length) return false;

  let chunkIdx = 0;
  let target = 0;
  let endAt = 0;

  const tick = (now) => {
    _mouthRaf = requestAnimationFrame(tick);
    if (now > endAt) {
      _mouthRaf && cancelAnimationFrame(_mouthRaf);
      _mouthRaf = null;
      setMouthLevel(0);
      if (chunkIdx < chunks.length - 1) return;
      setSpeaking(false);
      return;
    }
    const cur = mouthLevel();
    const k = target > cur ? 0.45 : 0.28;
    setMouthLevel(cur + (target - cur) * k);
  };

  const speakChunk = (idx) => {
    const chunk = chunks[idx];
    const u = new SpeechSynthesisUtterance(chunk);
    if (_ruVoice) u.voice = _ruVoice;
    u.lang = 'ru-RU';
    u.rate = opts.rate ?? 1.05;
    u.pitch = opts.pitch ?? 1.0;
    u.volume = opts.volume ?? 0.9;
    u.onstart = () => {
      setSpeaking(true);
      endAt = performance.now() + 1500 + chunk.length * 110;
      if (!_mouthRaf) _mouthRaf = requestAnimationFrame(tick);
      target = 0.45;
    };
    u.onboundary = (ev) => {
      const r = Math.random();
      target =
        r < 0.04 ? 0.92 + Math.random() * 0.08 :  // wide — very rare
        r < 0.55 ? 0.4 + Math.random() * 0.3 :    // normal
                   0.12 + Math.random() * 0.16;   // quiet
      if (ev && ev.name === 'word' && Math.random() < 0.15) target = 0.05;
    };
    u.onend = () => {
      chunkIdx = idx + 1;
      if (chunkIdx < chunks.length) {
        target = 0;
        speakChunk(chunkIdx);
      } else {
        _stopMouthLoop();
      }
    };
    u.onerror = () => { _stopMouthLoop(); };
    try { speechSynthesis.speak(u); }
    catch { _stopMouthLoop(); }
  };

  speakChunk(0);
  return true;
}

// ---------- Backend: local TTS service (Piper @ 127.0.0.1:8878) ----------
function _localTtsBase() {
  return (settings.tts_url || 'http://127.0.0.1:8878').replace(/\/$/, '');
}

// Build the fetch request for one chunk. Returns Promise<Blob> or throws.
async function _fetchTTSChunk(mode, chunk, opts) {
  if (mode === 'elevenlabs') {
    const url = `http://${settings.vps_host}/api/atrium/tts`;
    const r = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Atrium-Token': settings.atrium_token || '',
      },
      body: JSON.stringify({
        text: chunk,
        voice_id: settings.tts_voice_id || '0ArNnoIAWKlT4WweaVMY',
        model_id: settings.tts_model_id || 'eleven_multilingual_v2',
      }),
    });
    if (!r.ok) {
      const t = await r.text().catch(() => '');
      throw new Error(`elevenlabs proxy ${r.status}: ${t.slice(0, 200)}`);
    }
    return r.blob();
  }
  // local Piper
  const r = await fetch(`${_localTtsBase()}/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: chunk,
      voice: settings.tts_voice || 'irina',
      speed: opts.rate || 1.0,
    }),
  });
  if (!r.ok) {
    const t = await r.text().catch(() => '');
    throw new Error(`local ${r.status}: ${t.slice(0, 200)}`);
  }
  return r.blob();
}

// Sequential fetch + play loop shared by local and elevenlabs backends.
async function _speakRemote(mode, text, opts) {
  _stopAudio();
  _stopMouthLoop();
  // ElevenLabs handles long text natively but we still chunk to start
  // playback fast (first audio bytes on screen → user feedback).
  const maxLen = mode === 'elevenlabs' ? 320 : 240;
  const chunks = _splitForTTS(text, maxLen);
  if (!chunks.length) return false;
  setSpeaking(true);

  let aborted = false;
  let queueIdx = 0;
  const playNext = async () => {
    if (aborted || queueIdx >= chunks.length) {
      _stopAudio();
      _stopMouthLoop();
      return;
    }
    const chunk = chunks[queueIdx++];
    let blob;
    try {
      blob = await _fetchTTSChunk(mode, chunk, opts);
    } catch (e) {
      console.warn(`[voice] ${mode} TTS error:`, e.message);
      // Fallback for the rest of the text → browser
      const remaining = [chunk, ...chunks.slice(queueIdx)];
      _stopMouthLoop();
      _speakBrowser(remaining.join(' '), opts);
      return;
    }
    if (aborted) return;
    const url = URL.createObjectURL(blob);
    _audioObjectUrl = url;
    const el = new Audio();
    el.src = url;
    el.crossOrigin = 'anonymous';
    el.preload = 'auto';
    _audioEl = el;
    el.onended = () => {
      try { URL.revokeObjectURL(url); } catch {}
      if (_audioObjectUrl === url) _audioObjectUrl = null;
      _audioEl = null;
      setTimeout(playNext, 80);
    };
    el.onerror = (e) => {
      console.warn('[voice] audio playback error', e);
      _audioEl = null;
      playNext();
    };
    try {
      attachAudioEl(el);
      await el.play();
    } catch (e) {
      console.warn('[voice] play() refused', e);
      _audioEl = null;
      playNext();
    }
  };
  _localAbort = () => { aborted = true; };
  playNext();
  return true;
}
let _localAbort = null;

// ---------- shared helpers ----------
function _splitForTTS(text, maxLen = 220) {
  const out = [];
  const parts = text.split(/(?<=[.!?…])\s+|\n+/g).filter(Boolean);
  let buf = '';
  for (const p of parts) {
    if (!p) continue;
    if ((buf + ' ' + p).length > maxLen && buf) {
      out.push(buf.trim());
      buf = p;
    } else {
      buf = buf ? buf + ' ' + p : p;
    }
  }
  if (buf.trim()) out.push(buf.trim());
  const final = [];
  for (const c of out) {
    if (c.length <= maxLen) { final.push(c); continue; }
    for (let i = 0; i < c.length; i += maxLen) final.push(c.slice(i, i + maxLen));
  }
  return final;
}

export function speakText(text, opts = {}) {
  if (!isVoiceOn()) return false;
  const t = (text || '').trim();
  if (!t) return false;
  // Strip markdown / role-play asterisks for cleaner spoken output.
  const cleaned = t
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[#>*_~]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  // Stop any prior speech (override mid-stream).
  if (_localAbort) { try { _localAbort(); } catch {} _localAbort = null; }
  const mode = settings.voice_mode;
  if (mode === 'elevenlabs') return _speakRemote('elevenlabs', cleaned, opts);
  if (mode === 'local' || mode === 'cloned') return _speakRemote('local', cleaned, opts);
  return _speakBrowser(cleaned, opts);
}

// ---------- ElevenLabs probe ----------
export async function probeElevenLabs() {
  try {
    const url = `http://${settings.vps_host}/api/atrium/tts/health`;
    const r = await fetch(url, {
      headers: { 'X-Atrium-Token': settings.atrium_token || '' },
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) return { ok: false, error: j.error || `http ${r.status}` };
    return { ok: !!j.ok, info: j, error: j.error };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// ---------- service health probe ----------
export async function probeLocalTTS() {
  try {
    const r = await fetch(`${_localTtsBase()}/health`, { method: 'GET' });
    if (!r.ok) return { ok: false, error: `http ${r.status}` };
    const j = await r.json();
    return { ok: true, info: j };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

export async function listLocalVoices() {
  try {
    const r = await fetch(`${_localTtsBase()}/voices`, { method: 'GET' });
    if (!r.ok) return [];
    const j = await r.json();
    return j.voices || [];
  } catch {
    return [];
  }
}
