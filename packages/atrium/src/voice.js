/* voice.js — text-to-speech playback for Atrium.
 *
 * Two backends, selected via settings.voice_mode:
 *   - 'off'      — no speech (default until tested)
 *   - 'browser'  — Web Speech API (free, ru-RU voice from OS, instant). Useful
 *                  to verify the full pipeline today; not her cloned voice.
 *   - 'cloned'   — TTS service (Chatterbox/SoVITS, Этап 2 — позже). Will hit
 *                  POST /api/atrium/tts → audio chunks → MediaSource → mouth.
 *
 * Either backend feeds the SAME mouth-amplitude store (mouthLevel/speaking)
 * so the avatar lip-syncs identically. SonyaAvatar maps that to mouth frames
 * via thresholds + hysteresis (closed/quiet/active/loud).
 */
import { settings, setSpeaking, setMouthLevel, mouthLevel } from './store.js';

// --- voice picker (browser backend) ---
let _ruVoice = null;
let _voicesPolled = false;

function pickRuVoice() {
  if (typeof speechSynthesis === 'undefined') return null;
  const all = speechSynthesis.getVoices();
  if (!all.length) return null;
  // Prefer ru-RU female voices that ship with major OS TTS engines.
  const preferRu = all.filter((v) => /^ru/i.test(v.lang));
  // Heuristic: female-sounding common names if available.
  const femaleNames = /irina|tatyana|katya|svetlana|daria|milena|natasha|ekaterina|alena|alyona|ksenia/i;
  _ruVoice =
    preferRu.find((v) => femaleNames.test(v.name)) ||
    preferRu[0] ||
    all[0];
  _voicesPolled = true;
  return _ruVoice;
}

if (typeof speechSynthesis !== 'undefined') {
  // voices may load async; getVoices() is empty initially.
  speechSynthesis.addEventListener('voiceschanged', pickRuVoice);
  pickRuVoice();
}

// Cancel any in-flight speech and reset mouth state.
let _mouthRaf = null;
function _stopMouthLoop() {
  if (_mouthRaf) cancelAnimationFrame(_mouthRaf);
  _mouthRaf = null;
  setMouthLevel(0);
  setSpeaking(false);
}

export function isVoiceOn() {
  return settings.voice_mode && settings.voice_mode !== 'off';
}

export function stopVoice() {
  if (typeof speechSynthesis !== 'undefined') {
    try { speechSynthesis.cancel(); } catch {}
  }
  _stopMouthLoop();
}

// Backend: browser TTS via SpeechSynthesisUtterance.
// We can't tap the synth audio output directly (no AudioNode), so we drive the
// mouth amplitude from boundary events (per-word) + a smoothing rAF loop. The
// mouth opens/closes in sync with speech rhythm even if not pixel-perfect amp.
function _speakBrowser(text, opts) {
  if (!('speechSynthesis' in window)) return false;
  if (!_voicesPolled) pickRuVoice();
  speechSynthesis.cancel();
  _stopMouthLoop();

  // Browser TTS dies on very long strings. Chunk on sentence boundaries.
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
      // continue if more chunks
      if (chunkIdx < chunks.length - 1) return; // onend will speak next
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
        r < 0.12 ? 0.85 + Math.random() * 0.15 :
        r < 0.55 ? 0.4 + Math.random() * 0.3 :
                   0.12 + Math.random() * 0.18;
      if (ev && ev.name === 'word' && Math.random() < 0.15) target = 0.05;
    };
    u.onend = () => {
      chunkIdx = idx + 1;
      if (chunkIdx < chunks.length) {
        // brief silence between chunks (mouth closes)
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

// Split text into TTS-friendly chunks at sentence/clause boundaries, ≤maxLen each.
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
  // also hard-split anything still too long
  const final = [];
  for (const c of out) {
    if (c.length <= maxLen) { final.push(c); continue; }
    for (let i = 0; i < c.length; i += maxLen) final.push(c.slice(i, i + maxLen));
  }
  return final;
}

// Backend: cloned TTS service (Этап 2 — wires up later).
async function _speakCloned(text, opts) {
  // Placeholder: would POST text to /api/atrium/tts, get audio stream,
  // play via <audio> element, and call mouthAudio.attachAudioEl(el) so
  // mouthLevel comes from REAL amplitude (the production lip-sync path).
  // For now fall back to browser so the pipeline still works.
  return _speakBrowser(text, opts);
}

export function speakText(text, opts = {}) {
  if (!isVoiceOn()) return false;
  const t = (text || '').trim();
  if (!t) return false;
  // Strip markdown / role-play asterisks for cleaner spoken output.
  const cleaned = t
    .replace(/\*([^*]+)\*/g, '$1')   // *italic / actions* → text
    .replace(/`([^`]+)`/g, '$1')      // `code` → code
    .replace(/[#>*_~]/g, '')          // bare md markers
    .replace(/\s+/g, ' ')
    .trim();
  const mode = settings.voice_mode;
  if (mode === 'cloned') return _speakCloned(cleaned, opts);
  return _speakBrowser(cleaned, opts);
}
