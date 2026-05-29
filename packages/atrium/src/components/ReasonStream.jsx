/* ReasonStream — collapsible bottom panel with unified event stream.
 * Filters by src (active/worker/idle/skill/system).
 * Reply button on each row → inline composer → POST /api/atrium/nudge.
 *
 * См. UX_SKETCH.md §5.5 для дизайна.
 */
import { For, Show, createSignal } from 'solid-js';
import { feed, settings, updateSetting, updateFilter } from '../store.js';
import { sendNudge } from '../ws.js';

const FILTER_ORDER = ['active', 'worker', 'idle', 'skill', 'system'];

const SRC_TAG_LABEL = {
  active: 'active',
  worker: 'worker',
  idle: 'idle',
  skill: 'skill',
  system: 'system',
};

export default function ReasonStream() {
  // Map of seq → reply input state
  const [activeReply, setActiveReply] = createSignal({ seq: null, text: '', sending: false, error: '' });

  function toggleCollapse() {
    updateSetting('streams_collapsed', !settings.streams_collapsed);
  }

  function toggleFilter(src, e) {
    e.stopPropagation();
    updateFilter(src, !settings.streams_filters[src]);
  }

  function openReply(seq) {
    setActiveReply({ seq, text: '', sending: false, error: '' });
  }

  function closeReply() {
    setActiveReply({ seq: null, text: '', sending: false, error: '' });
  }

  async function submitReply(seq, session_id) {
    const text = activeReply().text.trim();
    if (!text) {
      closeReply();
      return;
    }
    setActiveReply({ ...activeReply(), sending: true });
    try {
      await sendNudge({ session_id: session_id || '', text, ref_seq: seq });
      closeReply();
    } catch (err) {
      setActiveReply({ ...activeReply(), sending: false, error: String(err.message || err) });
    }
  }

  // Filter visible events
  const visibleEvents = () =>
    feed.stream_events.filter((e) => settings.streams_filters[e.src] !== false);

  return (
    <section
      classList={{
        streams: true,
        collapsed: settings.streams_collapsed,
      }}
    >
      <div class="streams-header" onClick={toggleCollapse}>
        <span classList={{ title: true, live: feed.connected }}>REASON-STREAMS · {feed.connected ? 'live' : 'offline'}</span>
        <div class="filters" onClick={(e) => e.stopPropagation()}>
          <For each={FILTER_ORDER}>
            {(src) => (
              <span
                classList={{
                  filter: true,
                  active: settings.streams_filters[src] !== false,
                }}
                data-src={src}
                onClick={(e) => toggleFilter(src, e)}
              >
                {src}
              </span>
            )}
          </For>
        </div>
        <span class="toggle">⌃</span>
      </div>

      <div class="streams-body">
        <Show
          when={visibleEvents().length > 0}
          fallback={
            <div style="color: var(--ink-3); font-style: italic; padding: 20px; text-align: center;">
              {feed.connected ? 'тишина...' : 'нет соединения'}
            </div>
          }
        >
          <For each={visibleEvents()}>
            {(ev) => (
              <>
                <div class="stream-row" data-src={ev.src}>
                  <div class="src"></div>
                  <span class="sts">{ev.ts}</span>
                  <span class="body">
                    <span class="src-tag">{SRC_TAG_LABEL[ev.src] || ev.src}</span>
                    <span class="kind">{ev.kind}</span>
                    {ev.body}
                  </span>
                  <button class="reply-btn" title="reply" onClick={() => openReply(ev.seq)}>
                    ↳
                  </button>
                </div>

                <Show when={activeReply().seq === ev.seq}>
                  <div class="nudge-row">
                    <div class="src"></div>
                    <span class="label">↳ ивана</span>
                    <div class="input-area">
                      <input
                        type="text"
                        autofocus
                        placeholder="напиши ей..."
                        value={activeReply().text}
                        onInput={(e) =>
                          setActiveReply({ ...activeReply(), text: e.currentTarget.value })
                        }
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            submitReply(ev.seq, ev.session_id);
                          } else if (e.key === 'Escape') {
                            closeReply();
                          }
                        }}
                        disabled={activeReply().sending}
                      />
                      <button
                        class="send"
                        onClick={() => submitReply(ev.seq, ev.session_id)}
                        disabled={activeReply().sending}
                      >
                        {activeReply().sending ? 'sending' : 'enter ⏎'}
                      </button>
                    </div>
                    <Show when={activeReply().error}>
                      <div style="grid-column: 2 / -1; color: var(--acc-warn); font-size: 11px; margin-top: 4px;">
                        {activeReply().error}
                      </div>
                    </Show>
                  </div>
                </Show>
              </>
            )}
          </For>
        </Show>
      </div>
    </section>
  );
}
