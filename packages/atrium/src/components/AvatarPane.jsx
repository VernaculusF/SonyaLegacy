/* AvatarPane — её силуэт + status lines.
 * Click → open room view (placeholder для Этапа 1).
 */
import { Show, createSignal, createEffect } from 'solid-js';
import { feed, avatarGlow } from '../store.js';

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

function topDriveLabel(drives) {
  const entries = Object.entries(drives || {});
  if (!entries.length) return '';
  const [k, v] = entries.reduce((a, b) => (b[1] > a[1] ? b : a));
  if (v < 0.1) return 'нейтральна';
  return k;
}

export default function AvatarPane() {
  const [glowing, setGlowing] = createSignal(false);

  // Trigger flash CSS animation on every avatarGlow tick
  createEffect((prev) => {
    const cur = avatarGlow();
    if (prev !== undefined && cur !== prev) {
      setGlowing(true);
      setTimeout(() => setGlowing(false), 1500);
    }
    return cur;
  });

  function openRoom() {
    // Этап 1 placeholder — show a stub modal. Этап 2 will replace this
    // with real room view (voice mode entry point).
    alert('Room view — Этап 2 (voice mode + Live2D). Сейчас placeholder.');
  }

  return (
    <aside class="pane avatar-pane">
      <h2>SONYA</h2>
      <div
        classList={{ 'avatar-frame': true, glow: glowing() }}
        onClick={openRoom}
        title="войти в комнату (Этап 2)"
      >
        <div class="avatar-glow"></div>
        <SonyaSilhouette />
        <div class="avatar-hint">войти в комнату</div>
      </div>

      <div class="status-line">
        <span class="label">смотрит</span>
        ивана
      </div>
      <div class="status-line">
        <span class="label">воспринимает</span>
        {feed.her_typing ? 'печатает' : 'тишина'}
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

// Silver bob + black headband + black oversize tee silhouette.
// Static SVG для Этапа 1; в Этапе 2 заменяем на Live2D.
function SonyaSilhouette() {
  return (
    <svg class="avatar-svg" viewBox="0 0 200 240" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="hairGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#dde0e5" />
          <stop offset="1" stop-color="#a8acb3" />
        </linearGradient>
        <linearGradient id="skinGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#e0e2e6" />
          <stop offset="1" stop-color="#b0b3b8" />
        </linearGradient>
        <linearGradient id="shirtGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#1c1d20" />
          <stop offset="1" stop-color="#0a0b0d" />
        </linearGradient>
        <linearGradient id="legGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#c8cbd0" />
          <stop offset="1" stop-color="#90939a" />
        </linearGradient>
      </defs>
      <ellipse cx="88" cy="232" rx="9" ry="14" fill="url(#legGrad)" opacity="0.6" />
      <ellipse cx="112" cy="232" rx="9" ry="14" fill="url(#legGrad)" opacity="0.6" />
      <path
        d="M 60 110 Q 55 105 56 100 L 70 96 Q 85 90 100 90 Q 115 90 130 96 L 144 100 Q 145 105 140 110 L 145 215 Q 100 225 55 215 Z"
        fill="url(#shirtGrad)"
      />
      <path d="M 56 100 Q 50 115 54 130 L 60 132 Q 60 115 62 105 Z" fill="#0a0b0d" opacity="0.7" />
      <path
        d="M 144 100 Q 150 115 146 130 L 140 132 Q 140 115 138 105 Z"
        fill="#0a0b0d"
        opacity="0.7"
      />
      <path d="M 90 88 L 110 88 L 108 98 L 92 98 Z" fill="url(#skinGrad)" />
      <g transform="rotate(-3 100 60)">
        <ellipse cx="100" cy="60" rx="22" ry="28" fill="url(#skinGrad)" />
        <path
          d="M 78 50 Q 72 30 88 22 Q 100 16 115 22 Q 128 28 126 48 Q 128 70 122 84 L 122 88 L 116 88 L 116 70 Q 110 60 100 60 Q 88 60 84 70 L 84 88 L 78 88 Z"
          fill="url(#hairGrad)"
        />
        <path d="M 80 38 Q 92 35 102 42 Q 96 50 88 52 Q 80 50 80 42 Z" fill="url(#hairGrad)" />
        <path d="M 110 38 Q 122 35 124 50 Q 122 60 116 62 Q 110 56 110 46 Z" fill="url(#hairGrad)" />
        <path d="M 76 36 Q 100 20 124 36 L 124 42 Q 100 28 76 42 Z" fill="#0a0b0d" />
        <ellipse cx="92" cy="60" rx="2.5" ry="1.8" fill="#8aa3b8" opacity="0.5" />
        <ellipse cx="108" cy="60" rx="2.5" ry="1.8" fill="#8aa3b8" opacity="0.5" />
        <path
          d="M 96 74 Q 100 76 104 74"
          stroke="#8a7a78"
          stroke-width="0.8"
          fill="none"
          opacity="0.6"
        />
      </g>
    </svg>
  );
}
