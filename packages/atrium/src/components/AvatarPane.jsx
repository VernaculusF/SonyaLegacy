/* AvatarPane — 2D-аватар Сони (default) + status lines.
 * 3D VRM-режим опционально (settings.avatar_mode === '3d') — для будущего
 * (ходьба/тело). По умолчанию чистый 2D без рига.
 * Click → войти в комнату.
 */
import { Show, createSignal, createEffect, onMount, onCleanup, For } from 'solid-js';
import { feed, setFeed, settings, updateSetting, avatarGlow, speaking, simulateSpeech } from '../store.js';
import SonyaAvatar from './SonyaAvatar.jsx';
import { VrmViewer } from '../vrmViewer.js';
import { attachMic, stopMouthAudio, isMouthAudioActive } from '../mouthAudio.js';
import { speakText, stopVoice } from '../voice.js';

const EXPRESSION_LABEL = {
  neutral: 'спокойна',
  smile: 'улыбается',
  thinking: 'задумалась',
  tired: 'устала',
  sad: 'грустная',
  sad_tears: 'плачет',
  excited: 'оживлена',
  curious: 'любопытно',
  tender: 'нежная',
  annoyed: 'раздражена',
  angry: 'злится',
  shy: 'смущена',
  desire: 'желание',
  playful: 'игривая',
  calm: 'умиротворена',
  surprised: 'удивлена',
  joy: 'радуется',
};

// Markers Ivan can click to preview (dev affordance, hover to reveal).
const PREVIEW_MARKERS = [
  'neutral', 'calm', 'joy', 'tender', 'playful', 'shy', 'desire',
  'sad', 'sad_tears', 'angry', 'surprised', 'thinking',
];

export default function AvatarPane(props) {
  const [glowing, setGlowing] = createSignal(false);
  const [micOn, setMicOn] = createSignal(false);
  const [micErr, setMicErr] = createSignal('');
  const use3d = () => settings.avatar_mode === '3d';

  async function toggleMic() {
    if (micOn()) {
      stopMouthAudio();
      setMicOn(false);
      return;
    }
    try {
      await attachMic();
      setMicOn(true);
      setMicErr('');
    } catch (e) {
      setMicErr('нет доступа к микрофону');
      setMicOn(false);
    }
  }
  onCleanup(() => { if (isMouthAudioActive()) stopMouthAudio(); });

  // Flash glow + simulate a short talk animation whenever she sends dialog.
  createEffect((prev) => {
    const cur = avatarGlow();
    if (prev !== undefined && cur !== prev) {
      setGlowing(true);
      setTimeout(() => setGlowing(false), 1500);
      simulateSpeech(2400);
    }
    return cur;
  });

  function openRoom() {
    if (props.onEnterRoom) props.onEnterRoom();
  }

  return (
    <aside class="pane avatar-pane">
      <h2>SONYA</h2>
      <div
        classList={{ 'avatar-frame': true, glow: glowing(), speaking: speaking() }}
        onClick={openRoom}
        title="войти в комнату"
      >
        <div class="avatar-glow"></div>
        <Show when={use3d()} fallback={<SonyaAvatar expression={feed.current_expression} />}>
          <Vrm3D />
        </Show>
        <div class="avatar-hint">войти в комнату</div>
      </div>

      <div class="status-line">
        <span class="label">смотрит</span>
        ивана
      </div>
      <div class="status-line">
        <span class="label">воспринимает</span>
        {feed.her_typing ? 'печатает' : speaking() ? 'говорит' : 'тишина'}
      </div>
      <div class="status-line">
        <span class="label">чувствует</span>
        {EXPRESSION_LABEL[feed.current_expression] || feed.current_expression}
      </div>

      <Show when={feed.her_typing}>
        <div class="typing-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </Show>

      {/* dev preview: hover the pane to reveal emotion chips (test all sprites). */}
      <div class="emotion-preview">
        <For each={PREVIEW_MARKERS}>
          {(m) => (
            <button
              classList={{ chip: true, on: feed.current_expression === m }}
              onClick={() => setFeed('current_expression', m)}
              title={EXPRESSION_LABEL[m] || m}
            >
              {m}
            </button>
          )}
        </For>
        <button class="chip talk" onClick={() => simulateSpeech(2400)} title="имитация речи (без голоса)">▶ talk</button>
        <button
          classList={{ chip: true, voice: true, on: settings.voice_mode && settings.voice_mode !== 'off' }}
          onClick={() => {
            // Cycle: off → local → browser → off
            const cur = settings.voice_mode || 'off';
            const next = cur === 'off' ? 'local'
                       : cur === 'local' ? 'browser'
                       : 'off';
            updateSetting('voice_mode', next);
            if (next === 'off') stopVoice();
          }}
          title="режим голоса: off → local (Silero) → browser → off"
        >{settings.voice_mode === 'local' ? '🔊 local'
           : settings.voice_mode === 'browser' ? '🔊 browser'
           : settings.voice_mode === 'cloned' ? '🔊 cloned'
           : '🔇 voice'}</button>
        <button
          class="chip talk"
          onClick={() => speakText('Привет, малыш. Я тебя слышу.')}
          title="тестовая фраза вслух"
        >▶ say hi</button>
        <button
          classList={{ chip: true, mic: true, on: micOn() }}
          onClick={toggleMic}
          title="говори в микрофон — её рот двигается по громкости (тест lip-sync)"
        >{micOn() ? '■ mic' : '🎙 mic'}</button>
        <Show when={micErr()}><span class="mic-err">{micErr()}</span></Show>
      </div>
    </aside>
  );
}

// 3D VRM render — only when avatar_mode === '3d'. Kept for the future
// walking/body work; not the default path.
function Vrm3D() {
  const [status, setStatus] = createSignal('init');
  let canvasEl;
  let viewer;

  onMount(() => {
    const url = settings.avatar_model_url;
    if (!url || !canvasEl) {
      setStatus('none');
      return;
    }
    viewer = new VrmViewer({ framing: 'portrait' });
    viewer.onStatus = (s) => setStatus(s);
    try {
      viewer.mount(canvasEl);
      viewer.load(url).then(() => {
        viewer.setExpression(feed.current_expression || 'neutral');
      }).catch(() => setStatus('error'));
    } catch {
      setStatus('error');
    }
    createEffect(() => {
      const expr = feed.current_expression;
      if (viewer && status() === 'ready') viewer.setExpression(expr);
    });
  });
  onCleanup(() => { if (viewer) viewer.dispose(); });

  return (
    <>
      <canvas ref={canvasEl} class="avatar-canvas"></canvas>
      <Show when={status() === 'loading' || status() === 'init'}>
        <div class="avatar-loading">загружаю модель…</div>
      </Show>
    </>
  );
}
