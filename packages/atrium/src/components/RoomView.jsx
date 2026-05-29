/* RoomView — её комната. Полноэкранный 3D-вид (VRM в процедурной комнате).
 *
 * Этап 1/«сейчас»: настоящая 3D-сцена (не alert-заглушка) — комната + аватар
 * во весь рост, idle-анимации, мимика. Voice-mode UI (волны/субтитры/бюджет/
 * контролы) присутствует как каркас, но помечен «Этап 2» — реальные VAD/ASR/
 * TTS подключаются когда решится вопрос с GPU (см. ETAP2_RESEARCH).
 *
 * Esc / клик ⏏ — выйти. Дизайн — docs/atrium/mockups/room.html.
 */
import { onMount, onCleanup, createSignal, Show } from 'solid-js';
import { feed, settings } from '../store.js';
import { VrmViewer } from '../vrmViewer.js';

export default function RoomView(props) {
  let canvasEl;
  let viewer;
  const [status, setStatus] = createSignal('init');

  onMount(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') props.onClose?.();
    };
    window.addEventListener('keydown', onKey);

    const url = settings.avatar_model_url;
    if (url && canvasEl) {
      viewer = new VrmViewer({ framing: 'full', room: true });
      viewer.onStatus = (s) => setStatus(s);
      try {
        viewer.mount(canvasEl);
        viewer.load(url)
          .then(() => {
            viewer.setExpression(feed.current_expression || 'neutral');
            // Optional: load a real GLB room if configured.
            if (settings.room_model_url) {
              viewer.loadRoom(settings.room_model_url).catch(() => {});
            }
          })
          .catch((err) => {
            console.error('room VRM load failed', err);
            setStatus('error');
          });
      } catch (err) {
        console.error('room mount failed', err);
        setStatus('error');
      }
    } else {
      setStatus('none');
    }

    onCleanup(() => {
      window.removeEventListener('keydown', onKey);
      if (viewer) viewer.dispose();
    });
  });

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
          <canvas ref={canvasEl} class="room-canvas"></canvas>
          <Show when={status() === 'loading' || status() === 'init'}>
            <div class="room-loading">захожу в комнату…</div>
          </Show>
          <Show when={status() === 'error' || status() === 'none'}>
            <div class="room-loading">
              модель не загружена. задай avatar_model_url в настройках.
            </div>
          </Show>
        </div>

        {/* Voice-mode scaffold — Этап 2 (нужен GPU для TTS/ASR) */}
        <div class="room-voice">
          <div class="room-voice-badge">
            voice mode · Этап 2 (VAD + ASR + TTS — ждёт GPU)
          </div>
          <div class="room-voice-row">
            <div class="vm-speaker her idle">
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
