/* mouthAudio.js — drive the avatar mouth from REAL audio amplitude.
 *
 * Web Audio AnalyserNode → smoothed RMS → store.mouthLevel (0..1). The view
 * (SonyaAvatar) buckets that level into mouth frames (closed/quiet/open/wide).
 *
 * Two sources:
 *   - attachMic()        → microphone (test now: Ivan speaks → her mouth moves)
 *   - attachAudioEl(el)  → an <audio>/<video> element (real TTS playback, Этап 2)
 *
 * This is the production lip-sync path. The fake simulateSpeech() in store.js
 * is only a fallback when there's no audio.
 */
import { setSpeaking, setMouthLevel } from './store.js';

let ctx = null;
let analyser = null;
let raf = null;
let srcNode = null;
let micStream = null;
let dataArr = null;
let smooth = 0;

function ensureCtx() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    ctx = new AC();
  }
  return ctx;
}

// RMS → perceptual mouth level. Speech RMS sits ~0.02-0.30; we scale and
// soft-knee it so quiet speech still opens the mouth a bit and loud peaks
// reach the top. Attack fast (mouth snaps open), release slower (natural close).
function _loop() {
  raf = requestAnimationFrame(_loop);
  analyser.getByteTimeDomainData(dataArr);
  let sum = 0;
  for (let i = 0; i < dataArr.length; i++) {
    const v = (dataArr[i] - 128) / 128; // -1..1
    sum += v * v;
  }
  const rms = Math.sqrt(sum / dataArr.length); // 0..~1
  // noise gate: ignore room hum / faint background
  const gated = rms < 0.012 ? 0 : rms;
  // scale into 0..1. For TTS WAVs (peak-normalized to ~0.95), voiced RMS
  // sits around 0.15-0.25 with rare 0.35+ peaks. We want most syllables to
  // map to the "active" mouth frame and only emphatic peaks to "wide".
  // Multiplier 2.4 + soft compression keeps frame 3 rare.
  let level = Math.min(1, gated * 2.4);
  level = Math.pow(level, 1.0); // linear; was 0.85 (too aggressive lifting)
  const k = level > smooth ? 0.55 : 0.16; // attack / release
  smooth += (level - smooth) * k;
  if (smooth < 0.01) smooth = 0;
  setMouthLevel(smooth);
}

function _startAnalyser(node, connectToOutput) {
  analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  analyser.smoothingTimeConstant = 0.5;
  dataArr = new Uint8Array(analyser.fftSize);
  node.connect(analyser);
  if (connectToOutput) analyser.connect(ctx.destination);
  srcNode = node;
  setSpeaking(true);
  if (!raf) _loop();
}

// Microphone — test the pipeline now (Ivan's voice drives her mouth).
export async function attachMic() {
  const c = ensureCtx();
  await c.resume();
  micStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
  });
  const node = c.createMediaStreamSource(micStream);
  // do NOT route mic to output (no echo)
  _startAnalyser(node, false);
}

// Real TTS playback (Этап 2): pass the <audio> element that plays her voice.
// Safe to call multiple times — each call replaces the previous source/analyser
// without tearing down the AudioContext (re-creating it costs ~100ms and would
// drop the very next chunk).
export function attachAudioEl(el) {
  const c = ensureCtx();
  c.resume();
  // Disconnect previous audio source (don't kill mic-mode if active).
  if (raf && srcNode && srcNode !== el) {
    try { srcNode.disconnect(); } catch {}
  }
  let node;
  try {
    node = c.createMediaElementSource(el);
  } catch (e) {
    // Some browsers throw if the same element was already connected. Reuse.
    console.warn('[mouthAudio] createMediaElementSource:', e.message);
    return;
  }
  _startAnalyser(node, true);
}

export function stopMouthAudio() {
  if (raf) cancelAnimationFrame(raf);
  raf = null;
  if (micStream) {
    micStream.getTracks().forEach((t) => t.stop());
    micStream = null;
  }
  try { if (srcNode) srcNode.disconnect(); } catch {}
  srcNode = null;
  analyser = null;
  smooth = 0;
  setMouthLevel(0);
  setSpeaking(false);
}

export function isMouthAudioActive() {
  return !!raf;
}
