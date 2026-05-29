/* AvatarPane — 2D-аватар Сони (default) + status lines.
 * 3D VRM-режим опционально (settings.avatar_mode === '3d') — для будущего
 * (ходьба/тело). По умолчанию чистый 2D без рига.
 * Click → войти в комнату.
 */
import { Show, createSignal, createEffect, onMount, onCleanup } from 'solid-js';
import { feed, settings, avatarGlow, speaking, simulateSpeech } from '../store.js';
import SonyaAvatar from './SonyaAvatar.jsx';
import { VrmViewer } from '../vrmViewer.js';

const EXPRESSION_LABEL = {
  neutral: 'спокойна',
  smile: 'улыбается',
  thinking: 'задумалась',
  tired: 'устала',
  sad: 'грустная',
  excited: 'оживлена',
  curious: 'любопытно',
  tender: 'нежная',
  annoyed: 'раздражена',
};

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
