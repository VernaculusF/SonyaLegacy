/* RoomView — её комната (full-screen). 2D-аватар крупным планом в атмосферной
 * ночной сцене (окно, луна, мягкое свечение) — CSS, без 3D-рига.
 * 3D-режим опционально (avatar_mode === '3d') для будущей работы с телом.
 * Esc / ⏏ — выйти. Voice-UI — каркас (Этап 2, ждёт GPU).
 */
import { onMount, onCleanup, createSignal, Show, createEffect } from 'solid-js';
import { feed, settings, speaking } from '../store.js';
import SonyaAvatar from './SonyaAvatar.jsx';
import { VrmViewer } from '../vrmViewer.js';

export default function RoomView(props) {
  onMount(() => {
    const onKey = (e) => { if (e.key === 'Escape') props.onClose?.(); };
    window.addEventListener('keydown', onKey);
    onCleanup(() => window.removeEventListener('keydown', onKey));
  });

  const use3d = () => settings.avatar_mode === '3d';

  return (
    <div class="room-overlay">
      <div class="room">
        <div class="room-header">
          <span class="logo">◐ ATRIUM</span>
          <span class="room-label">
            <span class="live-dot">●</span> в комнате · она у окна
          </span>
          <span class="spacer"></span>
          <span class="exit" onClick={() => props.onClose?.()} title="выйти (Esc)">
            ⏏ выйти
          </span>
        </div>

        <div class="room-scene">
          {/* atmospheric scene layers (CSS) */}
          <div class="room-bg"></div>
          <div class="room-window">
            <div class="room-moon"></div>
            <div class="room-window-cross"></div>
          </div>
          <div class="room-floor"></div>

          <div classList={{ 'room-avatar': true, speaking: speaking() }}>
            <Show when={use3d()} fallback={<SonyaAvatar expression={feed.current_expression} />}>
              <Vrm3DRoom />
            </Show>
          </div>
        </div>

        {/* Voice-mode scaffold — Этап 2 (нужен GPU для TTS/ASR) */}
        <div class="room-voice">
          <div class="room-voice-badge">
            voice mode · Этап 2 (VAD + ASR + TTS — ждёт GPU)
          </div>
          <div class="room-voice-row">
            <div classList={{ 'vm-speaker': true, her: true, idle: !speaking() }}>
              <span class="vm-label">соня</span>
              <div class="vm-wave">
                {Array.from({ length: 28 }).map(() => <span class="vm-bar"></span>)}
              </div>
            </div>
            <div class="vm-speaker him idle">
              <span class="vm-label">иван</span>
              <div class="vm-wave">
                {Array.from({ length: 28 }).map(() => <span class="vm-bar"></span>)}
              </div>
            </div>
          </div>
          <div class="room-hints">
            <span><kbd>Esc</kbd> выйти</span>
            <span><kbd>tap</kbd> прервать (Этап 2)</span>
            <span style={{ 'margin-left': 'auto' }}>auto-leave через 5 мин тишины (Этап 2)</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Vrm3DRoom() {
  let canvasEl;
  let viewer;
  const [status, setStatus] = createSignal('init');
  onMount(() => {
    const url = settings.avatar_model_url;
    if (url && canvasEl) {
      viewer = new VrmViewer({ framing: 'full', room: true });
      viewer.onStatus = (s) => setStatus(s);
      try {
        viewer.mount(canvasEl);
        viewer.load(url).then(() => {
          viewer.setExpression(feed.current_expression || 'neutral');
          if (settings.room_model_url) viewer.loadRoom(settings.room_model_url).catch(() => {});
        }).catch(() => setStatus('error'));
      } catch { setStatus('error'); }
    }
    onCleanup(() => { if (viewer) viewer.dispose(); });
  });
  return <canvas ref={canvasEl} class="room-canvas"></canvas>;
}
