/* Dialog pane — chat bubbles + composer.
 *
 * Full primary I/O surface:
 *   - send text of any size (backend has no truncation on the message she answers)
 *   - attach files (image / gif / video / text / code) via 📎 or drag-drop / paste
 *   - render her replies + Ivan's messages with media inline, code blocks, and
 *     large text scrollable.
 */
import { For, Show, createEffect, createSignal } from 'solid-js';
import { feed, pushDialogMessage, prependDialogMessages } from '../store.js';
import { sendDialog, uploadAtriumFile, mediaUrl, loadDialogHistory } from '../ws.js';

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

// Split a message into plain-text and ```code``` segments for rendering.
function segmentText(text) {
  const out = [];
  const re = /```(\w*)\n?([\s\S]*?)```/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ type: 'text', value: text.slice(last, m.index) });
    out.push({ type: 'code', lang: m[1] || '', value: m[2] });
    last = re.lastIndex;
  }
  if (last < text.length) out.push({ type: 'text', value: text.slice(last) });
  return out.length ? out : [{ type: 'text', value: text }];
}

function MessageBody(props) {
  const segs = () => segmentText(props.text || '');
  return (
    <For each={segs()}>
      {(s) =>
        s.type === 'code' ? (
          <pre class="bubble-code"><code>{s.value}</code></pre>
        ) : (
          <span class="bubble-text">{s.value}</span>
        )
      }
    </For>
  );
}

function Attachment(props) {
  const a = props.att;
  const mime = (a.media_mime || '').toLowerCase();
  const name = a.name || (a.media_path ? String(a.media_path).replace(/\\/g, '/').split('/').pop() : 'file');
  // Resolve URL: prefer explicit name/url, fall back to media_path basename.
  const url = mediaUrl(a.name || a.url || a.media_path);
  const isImg = mime.startsWith('image/') && !mime.includes('gif');
  const isGif = mime.includes('gif');
  const isVideo = mime.startsWith('video/');
  const isAudio = mime.startsWith('audio/');

  return (
    <div class="att">
      <Show when={isImg || isGif}>
        <img class="att-img" src={url} alt={name} loading="lazy" />
      </Show>
      <Show when={isVideo}>
        <video class="att-video" src={url} controls preload="metadata"></video>
      </Show>
      <Show when={isAudio}>
        <audio class="att-audio" src={url} controls preload="none"></audio>
      </Show>
      <Show when={!isImg && !isGif && !isVideo && !isAudio}>
        <a class="att-file" href={url} target="_blank" rel="noopener">
          📎 {name}{a.media_kind ? ` · ${a.media_kind}` : ''}
        </a>
      </Show>
    </div>
  );
}

export default function DialogPane(props) {
  let scrollEl;
  let textareaEl;
  let fileInputEl;
  const [draft, setDraft] = createSignal('');
  const [sending, setSending] = createSignal(false);
  const [sendError, setSendError] = createSignal('');
  const [pending, setPending] = createSignal([]); // staged attachments (upload refs)
  const [uploading, setUploading] = createSignal(false);
  const [dragOver, setDragOver] = createSignal(false);
  const [loadingHistory, setLoadingHistory] = createSignal(false);
  const [historyExhausted, setHistoryExhausted] = createSignal(false);

  // Track if the user is near the bottom — only auto-scroll then.
  let _wasAtBottom = true;

  function _isNearBottom() {
    if (!scrollEl) return true;
    return (scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight) < 80;
  }

  async function loadOlderHistory() {
    if (loadingHistory() || historyExhausted()) return;
    const cur = feed.dialog_messages;
    // Find oldest numeric seq we have. Local echoes start with 'local-' string.
    const oldestSeq = cur.reduce((min, m) => {
      const s = typeof m.seq === 'number' ? m.seq : null;
      if (s == null) return min;
      return min == null || s < min ? s : min;
    }, null);
    setLoadingHistory(true);
    const prevHeight = scrollEl ? scrollEl.scrollHeight : 0;
    try {
      const r = await loadDialogHistory(oldestSeq || 0, 50);
      const msgs = (r.events || []).map((e) => {
        const isHis = e.kind === 'incoming.atrium_dialog' || e.kind === 'incoming.telegram_message';
        const payload = e.payload || {};
        const atts = Array.isArray(payload.attachments) ? payload.attachments : [];
        if (!atts.length && payload.media_kind) {
          atts.push({
            media_kind: payload.media_kind,
            media_mime: payload.media_mime,
            media_path: payload.media_path,
            name: payload.media_path ? String(payload.media_path).replace(/\\/g, '/').split('/').pop() : '',
          });
        }
        return {
          seq: e.seq,
          ts: e.ts,
          sender: isHis ? 'him' : 'her',
          text: e.text || '',
          attachments: atts,
        };
      });
      prependDialogMessages(msgs);
      if (!r.has_more) setHistoryExhausted(true);
    } catch (e) {
      setSendError('история: ' + (e.message || e));
    } finally {
      setLoadingHistory(false);
      // Restore scroll position so the view doesn't jump.
      queueMicrotask(() => {
        if (scrollEl) {
          const newHeight = scrollEl.scrollHeight;
          scrollEl.scrollTop = newHeight - prevHeight;
        }
      });
    }
  }

  function onScroll(e) {
    const el = e.currentTarget;
    if (el.scrollTop < 60) {
      loadOlderHistory();
    }
    _wasAtBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 80;
  }

  createEffect(() => {
    feed.dialog_messages.length;
    queueMicrotask(() => {
      if (scrollEl && _wasAtBottom) {
        scrollEl.scrollTo({ top: scrollEl.scrollHeight, behavior: 'smooth' });
      }
    });
  });

  function openRoom() {
    if (props.onEnterRoom) props.onEnterRoom();
  }

  async function uploadFiles(files) {
    if (!files || !files.length) return;
    setUploading(true);
    setSendError('');
    for (const f of files) {
      try {
        const ref = await uploadAtriumFile(f);
        setPending((cur) => [...cur, ref]);
      } catch (e) {
        setSendError('upload: ' + (e.message || e));
      }
    }
    setUploading(false);
  }

  function onPickFiles(e) {
    uploadFiles(Array.from(e.target.files || []));
    e.target.value = '';
  }

  function onPaste(e) {
    const items = e.clipboardData?.items || [];
    const files = [];
    for (const it of items) {
      if (it.kind === 'file') {
        const f = it.getAsFile();
        if (f) files.push(f);
      }
    }
    if (files.length) {
      e.preventDefault();
      uploadFiles(files);
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer?.files || []);
    if (files.length) uploadFiles(files);
  }

  function removePending(idx) {
    setPending((cur) => cur.filter((_, i) => i !== idx));
  }

  async function send() {
    const text = draft().trim();
    const atts = pending();
    if ((!text && !atts.length) || sending()) return;
    setSendError('');
    setSending(true);
    pushDialogMessage({
      seq: `local-${Date.now()}`,
      ts: new Date().toISOString(),
      sender: 'him',
      text,
      attachments: atts,
    });
    setDraft('');
    setPending([]);
    if (textareaEl) textareaEl.style.height = 'auto';
    // User just sent — they want to see their message AND the reply at
    // the bottom. Force the auto-scroll flag and scroll smoothly so the
    // local echo is in view even if the textarea growth had nudged the
    // viewport up earlier.
    _wasAtBottom = true;
    queueMicrotask(() => {
      if (scrollEl) {
        scrollEl.scrollTo({ top: scrollEl.scrollHeight, behavior: 'smooth' });
      }
    });
    try {
      await sendDialog(text, atts);
    } catch (err) {
      setSendError(String(err.message || err));
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function autoGrow(e) {
    setDraft(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
  }

  return (
    <main
      classList={{ 'dialog-pane': true, 'drag-over': dragOver() }}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      <div class="dialog-scroll" ref={scrollEl} onScroll={onScroll}>
        <Show when={loadingHistory()}>
          <div class="history-loader">загружаю историю…</div>
        </Show>
        <Show when={historyExhausted() && feed.dialog_messages.length > 0}>
          <div class="history-loader exhausted">— начало диалога —</div>
        </Show>
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
              <div class="msg-row" data-seq={String(m.seq)}>
                <div classList={{ ts: true, 'her-ts': m.sender === 'her', 'him-ts': m.sender === 'him' }}>
                  <span class="msg-name">{m.sender === 'her' ? 'соня' : 'иван'}</span>
                  <span class="msg-time">{formatTime(m.ts)}</span>
                </div>
                <div classList={{ bubble: true, [m.sender]: true }}>
                  <Show when={m.text}>
                    <MessageBody text={m.text} />
                  </Show>
                  <Show when={m.attachments && m.attachments.length}>
                    <div class="bubble-atts">
                      <For each={m.attachments}>
                        {(a) => <Attachment att={a} />}
                      </For>
                    </div>
                  </Show>
                </div>
              </div>
            )}
          </For>
        </Show>
        <Show when={feed.her_typing}>
          <div class="typing-row">
            <span class="typing-name">соня</span>
            <span class="typing-bubble">
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
            </span>
          </div>
        </Show>
      </div>

      <div class="composer">
        <Show when={sendError()}>
          <div class="composer-error">{sendError()}</div>
        </Show>

        <Show when={pending().length || uploading()}>
          <div class="composer-attachments">
            <For each={pending()}>
              {(a, i) => (
                <div class="pending-att" title={a.orig_name || a.name}>
                  <span class="pending-kind">{a.media_kind || 'файл'}</span>
                  <span class="pending-name">{a.orig_name || a.name}</span>
                  <button class="pending-x" onClick={() => removePending(i())} title="убрать">×</button>
                </div>
              )}
            </For>
            <Show when={uploading()}>
              <div class="pending-att uploading">загрузка…</div>
            </Show>
          </div>
        </Show>

        <div class="composer-row">
          <button
            class="attach-btn"
            title="прикрепить файл"
            onClick={() => fileInputEl?.click()}
          >
            <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
              <path d="M21 11.5l-8.5 8.5a5 5 0 01-7-7l8.5-8.5a3.5 3.5 0 015 5l-8.5 8.5a2 2 0 01-3-3l8-8"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <input
            ref={fileInputEl}
            type="file"
            multiple
            style="display:none"
            onChange={onPickFiles}
          />
          <textarea
            ref={textareaEl}
            placeholder="напиши ей... (можно вставить/перетащить файл)"
            value={draft()}
            disabled={sending()}
            onInput={autoGrow}
            onKeyDown={onKeyDown}
            onPaste={onPaste}
            rows="1"
          ></textarea>
          <button
            class="send-btn"
            title="отправить (Enter)"
            disabled={sending() || (!draft().trim() && !pending().length)}
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
            title="войти в комнату"
            onClick={openRoom}
          >
            <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
              <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" stroke-width="1.5" />
              <path d="M5 11a7 7 0 0014 0M12 18v3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
          </button>
        </div>
        <div class="composer-hint">
          <span class="hint-key">Enter</span> отправить ·
          <span class="hint-key">Shift+Enter</span> перенос ·
          <span class="hint-key">📎</span> файл ·
          <span class="hint-key">drag/paste</span> вставить
        </div>
      </div>
    </main>
  );
}
