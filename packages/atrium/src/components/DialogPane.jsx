/* Dialog pane — chat bubbles + composer.
 * Этап 1: composer write disabled; we read-only show messages from feed.
 * Sending dialog/voice from Atrium pending Этап 2 (need TG-bridge integration
 * or admin inject endpoint).
 */
import { For, Show, createEffect, createSignal } from 'solid-js';
import { feed, pushDialogMessage } from '../store.js';
import { sendDialog } from '../ws.js';
import { stopVoice } from '../voice.js';

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

export default function DialogPane(props) {
  let scrollEl;
  let textareaEl;
  const [draft, setDraft] = createSignal('');
  const [sending, setSending] = createSignal(false);
  const [sendError, setSendError] = createSignal('');

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
    if (props.onEnterRoom) props.onEnterRoom();
  }

  async function send() {
    const text = draft().trim();
    if (!text || sending()) return;
    // Cut any in-flight speech so she doesn't keep talking over Ivan's new turn.
    stopVoice();
    setSendError('');
    setSending(true);
    // Optimistic echo so Ivan sees his message immediately. The backend
    // records incoming.atrium_dialog; the WS feed won't echo it back as a
    // dialog bubble (only her replies + telegram incoming render), so the
    // optimistic push is the canonical local copy.
    pushDialogMessage({
      seq: `local-${Date.now()}`,
      ts: new Date().toISOString(),
      sender: 'him',
      text,
    });
    setDraft('');
    if (textareaEl) textareaEl.style.height = 'auto';
    try {
      await sendDialog(text);
    } catch (err) {
      setSendError(String(err.message || err));
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e) {
    // Enter sends; Shift+Enter newline
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function autoGrow(e) {
    setDraft(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px';
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
        <Show when={sendError()}>
          <div class="composer-error">{sendError()}</div>
        </Show>
        <div class="composer-row">
          <textarea
            ref={textareaEl}
            placeholder="напиши ей..."
            value={draft()}
            disabled={sending()}
            onInput={autoGrow}
            onKeyDown={onKeyDown}
            rows="1"
          ></textarea>
          <button
            class="send-btn"
            title="отправить (Enter)"
            disabled={sending() || !draft().trim()}
            onClick={send}
          >
            <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
              <path
                d="M4 12l16-8-6 16-3-7-7-1z"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linejoin="round"
              />
            </svg>
          </button>
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
          <span class="hint-key">Enter</span> отправить ·
          <span class="hint-key">Shift+Enter</span> перенос ·
          <span class="hint-key">click 🎙</span> комната (Этап 2)
        </div>
      </div>
    </main>
  );
}
