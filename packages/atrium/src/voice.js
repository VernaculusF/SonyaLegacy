/* voice.js — text-to-speech playback for Atrium.
 *
 * Three backends, selected via settings.voice_mode:
 *   - 'off'      — no speech (default until user enables).
 *   - 'browser'  — Web Speech API (free, ru-RU OS voice). Quick fallback / test
 *                  path. Mouth driven by boundary events + smoothing.
 *   - 'local'    — local TTS service (services/tts/server.py @ 127.0.0.1:8878).
 *                  Returns WAV; played through <audio> + AudioContext analyser
 *                  → REAL amplitude-driven lip-sync via mouthAudio.attachAudioEl.
 *                  Currently Silero v4_ru (4 RU voices). Later swap to XTTS-v2
 *                  for cloned voice — same HTTP contract.
 *
 * Either backend feeds the SAME mouth-amplitude store (mouthLevel/speaking)
 * so the avatar lip-syncs identically. SonyaAvatar maps that to mouth frames.
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

// ---------- Backend: local TTS service (Silero @ 127.0.0.1:8878) ----------
function _localTtsBase() {
  return (settings.tts_url || 'http://127.0.0.1:8878').replace(/\/$/, '');
}

async function _speakLocal(text, opts) {
  _stopAudio();
  _stopMouthLoop();
  // chunk so a long reply doesn't wait for full synth
  const chunks = _splitForTTS(text, 240);
  if (!chunks.length) return false;
  setSpeaking(true);

  // Sequential playback: synth+play chunk[i], onended → next.
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
      const r = await fetch(`${_localTtsBase()}/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: chunk,
          voice: settings.tts_voice || 'baya',
          speed: opts.rate || 1.0,
        }),
      });
      if (!r.ok) {
        const errTxt = await r.text().catch(() => '');
        console.warn('[voice] local TTS error', r.status, errTxt);
        // graceful fallback: speak this chunk via browser, then continue
        await new Promise((res) => {
          const u = new SpeechSynthesisUtterance(chunk);
          if (_ruVoice) u.voice = _ruVoice;
          u.lang = 'ru-RU';
          u.onend = u.onerror = () => res();
          speechSynthesis.speak(u);
        });
        return playNext();
      }
      blob = await r.blob();
    } catch (e) {
      console.warn('[voice] local TTS unreachable, falling back to browser:', e);
      // service down → fall back fully to browser for the rest
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
      // brief pause so next chunk reads as a sentence boundary
      setTimeout(playNext, 80);
    };
    el.onerror = (e) => {
      console.warn('[voice] audio playback error', e);
      _audioEl = null;
      playNext();
    };
    try {
      // Wire amplitude → mouth via Web Audio analyser (real lip-sync).
      attachAudioEl(el);
      await el.play();
    } catch (e) {
      console.warn('[voice] play() refused', e);
      _audioEl = null;
      playNext();
    }
  };
  // expose a way to abort if stopVoice() is called mid-stream
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
  if (mode === 'local' || mode === 'cloned') return _speakLocal(cleaned, opts);
  return _speakBrowser(cleaned, opts);
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
