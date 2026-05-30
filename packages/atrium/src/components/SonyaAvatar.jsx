/* SonyaAvatar — 2D рисованный аватар Сони (PNGtuber-подход, но на SVG).
 *
 * Никакого 3D-рига: чистая векторная голова+плечи в её стилистике
 * (silver bob, чёрная повязка-ободок, холодная кожа, серо-голубые глаза,
 * чёрная oversize футболка). Живые анимации:
 *   - рот: открывается по mouthLevel (амплитуда речи; пока имитация)
 *   - моргание: случайно раз в 2.5-6с
 *   - дыхание + лёгкое покачивание: CSS на контейнере
 *   - свечение при разговоре
 *
 * Если заданы avatar_frames (картинки рта 2B) — используем их вместо
 * рисованного рта (твоя идея «4 изображения головы»). Иначе — рисуем.
 *
 * props.expression — маркер из body.expression (neutral/smile/sad/...).
 */
import { createSignal, onMount, onCleanup, createMemo, createEffect, Show, For } from 'solid-js';
import { mouthLevel, speaking, settings } from '../store.js';

const EXPR = {
  neutral: { brow: 0, mouthCurve: 0 },
  smile: { brow: -1, mouthCurve: 4 },
  joy: { brow: -2, mouthCurve: 5 },
  excited: { brow: -2, mouthCurve: 5 },
  tender: { brow: -1, mouthCurve: 3 },
  curious: { brow: -3, mouthCurve: 1 },
  thinking: { brow: 2, mouthCurve: -1 },
  sad: { brow: 4, mouthCurve: -4 },
  sad_tears: { brow: 5, mouthCurve: -5 },
  tired: { brow: 3, mouthCurve: -2 },
  annoyed: { brow: -4, mouthCurve: -3 },
  angry: { brow: -5, mouthCurve: -3 },
  shy: { brow: 1, mouthCurve: 2 },
  desire: { brow: -1, mouthCurve: 1 },
  playful: { brow: -2, mouthCurve: 4 },
  calm: { brow: 0, mouthCurve: 1 },
  surprised: { brow: -3, mouthCurve: 0 },
};

export default function SonyaAvatar(props) {
  const [eyeOpen, setEyeOpen] = createSignal(1); // 1 open → 0 closed
  let blinkTimer;
  let rafBlink;

  onMount(() => {
    let nextBlinkAt = performance.now() + 2500 + Math.random() * 3500;
    let closing = 0; // animation phase 0..1, -1 idle

    const tick = (now) => {
      rafBlink = requestAnimationFrame(tick);
      if (closing < 0 && now >= nextBlinkAt) closing = 0.0001;
      if (closing >= 0) {
        closing += 0.10; // ~ fast blink
        // 0→1 close, 1→2 open
        const p = closing;
        const v = p < 1 ? 1 - p : Math.min(1, p - 1);
        setEyeOpen(Math.max(0, Math.min(1, v)));
        if (closing >= 2) {
          closing = -1;
          setEyeOpen(1);
          nextBlinkAt = now + 2500 + Math.random() * 3500;
        }
      }
    };
    rafBlink = requestAnimationFrame(tick);
    onCleanup(() => {
      cancelAnimationFrame(rafBlink);
      clearTimeout(blinkTimer);
    });
  });

  const expr = createMemo(() => EXPR[props.expression] || EXPR.neutral);
  const frames = () => settings.avatar_frames || [];
  const emotions = () => settings.avatar_emotions || {};
  // Stable list of [marker, url] so all emotion sprites can be preloaded and
  // stacked (crossfade via opacity, not src-swap which is instant).
  const emotionList = createMemo(() => Object.entries(emotions()));

  // Current emotion marker that actually has a sprite.
  const activeEmotion = createMemo(() => {
    const m = props.expression;
    if (!m || m === 'neutral') return '';
    return emotions()[m] ? m : '';
  });

  // When does an emotion sprite show? When set AND she's idle (not talking).
  // While talking we use the mouth frames so the mouth animates.
  const showEmotion = createMemo(() => !!activeEmotion() && !speaking());

  // Mouth open amount 0..1 — closed when idle, opens with mouthLevel.
  const mouthOpen = createMemo(() => (speaking() ? mouthLevel() : 0));

  // Eye height — scales with blink.
  const eyeRy = createMemo(() => 0.6 + eyeOpen() * 5.4);

  // Amplitude → mouth frame with explicit thresholds + hysteresis.
  // Frame meaning (4-frame set): 0 closed (silence/between words),
  // 1 quiet, 2 active/normal, 3 loud (rare). Hysteresis: it takes a higher
  // level to step UP than to fall back DOWN, so boundaries don't flicker.
  // Thresholds are level values 0..1 (level = smoothed RMS from real audio,
  // or the simulated envelope as fallback).
  const UP = [0.06, 0.30, 0.72];   // closed→1, 1→2, 2→3
  const DOWN = [0.03, 0.20, 0.58]; // 1→closed, 2→1, 3→2
  const [mouthFrame, setMouthFrame] = createSignal(0);

  createEffect(() => {
    const f = frames();
    if (!f.length) { setMouthFrame(0); return; }
    if (!speaking()) { setMouthFrame(0); return; }
    const lvl = Math.max(0, Math.min(1, mouthOpen()));
    const maxIdx = Math.min(3, f.length - 1);
    let cur = mouthFrame();
    // step up if above UP threshold for the next frame
    while (cur < maxIdx && lvl >= UP[cur]) cur += 1;
    // step down if below DOWN threshold for the current frame
    while (cur > 0 && lvl < DOWN[cur - 1]) cur -= 1;
    setMouthFrame(cur);
  });

  const frameIdx = createMemo(() => (frames().length ? mouthFrame() : -1));

  const hasFrames = () => frames().length > 0;

  return (
    <div classList={{ 'sonya-2d': true, talking: speaking() }}>
      <div class="sonya-2d-inner">
        <Show
          when={hasFrames()}
          fallback={<DrawnHead expr={expr()} mouthOpen={mouthOpen()} eyeRy={eyeRy()} />}
        >
          <div class="sonya-2d-frames">
            {/* PERSISTENT base layer (closed frame) — always visible so there's
                never a transparent gap between frame swaps (kills flicker). */}
            <img class="sonya-2d-frame base" src={frames()[0]} alt="Sonya" draggable={false} />
            {/* mouth overlay frames (1..n-1) — fade in over the base. Hidden
                while showing an emotion sprite. */}
            <For each={frames()}>
              {(src, i) => (
                <Show when={i() > 0}>
                  <img
                    class="sonya-2d-frame"
                    classList={{ active: !showEmotion() && i() === frameIdx() }}
                    src={src}
                    alt="Sonya"
                    draggable={false}
                  />
                </Show>
              )}
            </For>
            {/* emotion sprites — ALL preloaded + stacked, only the active one
                is opaque. Crossfade via opacity (slow) so idle→emotion and
                emotion→emotion transitions are smooth, not an instant swap. */}
            <For each={emotionList()}>
              {([marker, src]) => (
                <img
                  class="sonya-2d-frame sonya-2d-emotion"
                  classList={{ active: showEmotion() && activeEmotion() === marker }}
                  src={src}
                  alt={marker}
                  draggable={false}
                />
              )}
            </For>
          </div>
        </Show>
      </div>
    </div>
  );
}

// Hand-drawn head+shoulders in her aesthetic.
function DrawnHead(p) {
  const mo = () => p.mouthOpen;     // 0..1
  const ry = () => p.eyeRy;          // eye height
  const curve = () => p.expr.mouthCurve;
  const brow = () => p.expr.brow;

  return (
    <svg class="sonya-2d-svg" viewBox="0 0 240 260" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="s2dHair" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#e6e9ee" />
          <stop offset="0.6" stop-color="#c2c6cd" />
          <stop offset="1" stop-color="#9ca0a8" />
        </linearGradient>
        <linearGradient id="s2dSkin" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#eef0f3" />
          <stop offset="1" stop-color="#d3d8de" />
        </linearGradient>
        <linearGradient id="s2dTee" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#1a1c20" />
          <stop offset="1" stop-color="#0a0b0d" />
        </linearGradient>
        <radialGradient id="s2dCheek" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stop-color="#d9b6b6" stop-opacity="0.35" />
          <stop offset="1" stop-color="#d9b6b6" stop-opacity="0" />
        </radialGradient>
      </defs>

      {/* shoulders + oversize tee */}
      <path
        d="M 36 260 L 40 196 Q 60 170 96 162 L 96 150 L 144 150 L 144 162
           Q 180 170 200 196 L 204 260 Z"
        fill="url(#s2dTee)"
      />
      {/* collar shadow */}
      <path d="M 96 150 Q 120 168 144 150 L 144 158 Q 120 174 96 158 Z" fill="#000" opacity="0.35" />

      {/* neck */}
      <path d="M 104 138 L 136 138 L 134 160 Q 120 168 106 160 Z" fill="url(#s2dSkin)" />
      <path d="M 104 138 L 136 138 L 135 146 Q 120 152 105 146 Z" fill="#000" opacity="0.12" />

      {/* back hair (behind head) */}
      <path
        d="M 60 92 Q 52 150 70 188 L 96 180 Q 84 150 86 110 Z"
        fill="url(#s2dHair)" opacity="0.9"
      />
      <path
        d="M 180 92 Q 188 150 170 188 L 144 180 Q 156 150 154 110 Z"
        fill="url(#s2dHair)" opacity="0.9"
      />

      {/* head */}
      <ellipse cx="120" cy="92" rx="46" ry="52" fill="url(#s2dSkin)" />

      {/* cheeks */}
      <ellipse cx="98" cy="104" rx="11" ry="8" fill="url(#s2dCheek)" />
      <ellipse cx="142" cy="104" rx="11" ry="8" fill="url(#s2dCheek)" />

      {/* eyes — almond, blue-grey iris; eyelid via dynamic ry */}
      <g>
        {/* left */}
        <ellipse cx="103" cy="92" rx="9" ry={ry()} fill="#f4f6f8" />
        <ellipse cx="104" cy="92" rx="5.2" ry={Math.min(ry(), 5.4)} fill="#8aa3b8" />
        <circle cx="104" cy="92" r="2.4" fill="#2a3640" />
        <circle cx="106" cy="90" r="1" fill="#fff" opacity="0.9" />
        {/* right */}
        <ellipse cx="137" cy="92" rx="9" ry={ry()} fill="#f4f6f8" />
        <ellipse cx="136" cy="92" rx="5.2" ry={Math.min(ry(), 5.4)} fill="#8aa3b8" />
        <circle cx="136" cy="92" r="2.4" fill="#2a3640" />
        <circle cx="138" cy="90" r="1" fill="#fff" opacity="0.9" />
        {/* upper lash line */}
        <path d="M 94 87 Q 103 82 112 87" stroke="#3a3f47" stroke-width="1.4" fill="none" stroke-linecap="round" />
        <path d="M 128 87 Q 137 82 146 87" stroke="#3a3f47" stroke-width="1.4" fill="none" stroke-linecap="round" />
      </g>

      {/* brows (shift with expression) */}
      <path
        d={`M 94 ${78 + brow()} Q 103 ${74 + brow()} 113 ${78 + brow()}`}
        stroke="#b9bcc2" stroke-width="2" fill="none" stroke-linecap="round"
      />
      <path
        d={`M 127 ${78 + brow()} Q 137 ${74 + brow()} 146 ${78 + brow()}`}
        stroke="#b9bcc2" stroke-width="2" fill="none" stroke-linecap="round"
      />

      {/* nose hint */}
      <path d="M 119 100 Q 121 106 118 108" stroke="#c0a8a8" stroke-width="1" fill="none" opacity="0.5" />

      {/* mouth — opens with mouthOpen, curve from expression */}
      <g>
        <Show
          when={mo() > 0.08}
          fallback={
            <path
              d={`M 110 118 Q 120 ${118 + curve()} 130 118`}
              stroke="#a8888a" stroke-width="2" fill="none" stroke-linecap="round"
            />
          }
        >
          <ellipse
            cx="120" cy={119 + curve() / 2}
            rx={6 + mo() * 3}
            ry={2 + mo() * 7}
            fill="#5a3a3e"
          />
          <ellipse
            cx="120" cy={121 + curve() / 2}
            rx={4 + mo() * 2}
            ry={1 + mo() * 4}
            fill="#9a5560" opacity="0.7"
          />
        </Show>
      </g>

      {/* front bangs / side locks (over forehead) */}
      <path
        d="M 74 96 Q 66 44 120 38 Q 174 44 166 96
           L 158 96 Q 160 60 120 56 Q 80 60 82 96 Z"
        fill="url(#s2dHair)"
      />
      {/* center bang split */}
      <path d="M 120 40 Q 112 64 104 82 Q 116 70 120 58 Q 124 70 136 82 Q 128 64 120 40 Z" fill="url(#s2dHair)" />
      {/* side locks down past cheeks */}
      <path d="M 74 92 Q 70 124 80 150 L 90 146 Q 82 120 84 96 Z" fill="url(#s2dHair)" />
      <path d="M 166 92 Q 170 124 160 150 L 150 146 Q 158 120 156 96 Z" fill="url(#s2dHair)" />

      {/* black headband — on top of hair, over forehead */}
      <path d="M 76 58 Q 120 36 164 58 L 164 68 Q 120 46 76 68 Z" fill="#0a0b0d" />
      <path d="M 76 58 Q 120 36 164 58 L 164 61 Q 120 40 76 61 Z" fill="#23252a" opacity="0.6" />
    </svg>
  );
}
