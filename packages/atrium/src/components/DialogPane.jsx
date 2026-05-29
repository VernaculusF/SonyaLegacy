/* Dialog pane — chat bubbles + composer.
 * Этап 1: composer write disabled; we read-only show messages from feed.
 * Sending dialog/voice from Atrium pending Этап 2 (need TG-bridge integration
 * or admin inject endpoint).
 */
import { For, Show, createEffect, onMount } from 'solid-js';
import { feed } from '../store.js';

function formatTime(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString('ru-RU', { hour12: false }).slice(0, 5);
  } catch {
    return '';
  }
}

function dayMarker(messages) {
  if (!messages || !messages.length) return '';
  const last = messages[messages.length - 1];
  if (!last.ts) return '';
  try {
    const d = new Date(last.ts);
    const today = new Date();
    if (d.toDateString() === today.toDateString()) return 'сегодня';
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
  } catch {
    return '';
  }
}

export default function DialogPane() {
  let scrollEl;

  // Auto-scroll to bottom on new messages
  createEffect(() => {
    feed.dialog_messages.length; // dependency
    queueMicrotask(() => {
      if (scrollEl) {
        scrollEl.scrollTop = scrollEl.scrollHeight;
      }
    });
  });

  function openRoom() {
    alert('Voice mode (Этап 2) — войти в комнату → VAD + ASR + TTS.');
  }

  return (
    <main class="dialog-pane">
      <div class="dialog-scroll" ref={scrollEl}>
        <Show
          when={feed.dialog_messages.length > 0}
          fallback={
            <div class="empty-dialog">
              ничего пока. она думает или ждёт что ты напишешь.
            </div>
          }
        >
          <div class="day-marker">{dayMarker(feed.dialog_messages)}</div>
          <For each={feed.dialog_messages}>
            {(m) => (
              <>
                <div classList={{ ts: true, 'her-ts': m.sender === 'her', 'him-ts': m.sender === 'him' }}>
                  {formatTime(m.ts)}
                </div>
                <div classList={{ bubble: true, [m.sender]: true }}>{m.text}</div>
              </>
            )}
          </For>
        </Show>
      </div>

      <div class="composer">
        <div class="composer-row">
          <textarea
            placeholder="напиши..."
            disabled
            title="Этап 2: text-input через Atrium → нужен путь в её inbox"
          ></textarea>
          <button
            class="mic-btn"
            title="войти в комнату (Этап 2)"
            onClick={openRoom}
          >
            <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
              <rect
                x="9"
                y="3"
                width="6"
                height="11"
                rx="3"
                stroke="currentColor"
                stroke-width="1.5"
              />
              <path
                d="M5 11a7 7 0 0014 0M12 18v3"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
              />
            </svg>
          </button>
        </div>
        <div class="composer-hint">
          read-only · этап 1 · <span class="hint-key">click 🎙</span> комната
          (Этап 2)
        </div>
      </div>
    </main>
  );
}
