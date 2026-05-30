/* AvatarPane — крупный 2D-аватар Сони для повседневного взаимодействия.
 *
 * Это НЕ комната (комната — для взаимодействия с «телом», отдельный overlay).
 * Здесь Иван видит крупно какие эмоции она выбирает во время диалога.
 *
 * Эмоции/выражение выбирает ТОЛЬКО Соня (через body.expression). Никаких
 * dev-кнопок выбора — только живой аватар.
 *
 * 3D VRM-режим опционально (settings.avatar_mode === '3d') — для будущего.
 * Click → войти в комнату.
 */
import { Show, createSignal, createEffect, onMount, onCleanup } from 'solid-js';
import { feed, settings, avatarGlow, speaking, simulateSpeech } from '../store.js';
import SonyaAvatar from './SonyaAvatar.jsx';
import { VrmViewer } from '../vrmViewer.js';

export default function AvatarPane(props) {
  const [glowing, setGlowing] = createSignal(false);
  const use3d = () => settings.avatar_mode === '3d';

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
