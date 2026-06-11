/* ReasonStream — collapsible bottom panel with unified event stream.
 * Filters by src (active/worker/idle/skill/system).
 * Reply button on each row → inline composer → POST /api/atrium/nudge.
 *
 * См. UX_SKETCH.md §5.5 для дизайна.
 */
import { For, Show, createSignal, onCleanup, onMount } from 'solid-js';
import { feed, settings, updateSetting, updateFilter, prependStreamEvents } from '../store.js';
import { sendNudge, loadEventHistory } from '../ws.js';

const FILTER_ORDER = ['active', 'worker', 'idle', 'skill', 'system'];

const SRC_TAG_LABEL = {
  active: 'active',
  worker: 'worker',
  idle: 'idle',
  skill: 'skill',
  system: 'system',
};

const DRIVE_ORDER = ['curiosity', 'relational_focus', 'pending_debt', 'boredom'];

function isProjectTraceNoise(ev) {
  return ev.kind?.startsWith('subagent.') || ev.kind?.startsWith('project.');
}

function isDialogAgentStep(ev) {
  return ev.kind === 'internal.agent_step' && ev.payload?.tool === 'chat.dialog';
}

export default function ReasonStream(props) {
  // Map of seq → reply input state
  const [activeReply, setActiveReply] = createSignal({ seq: null, text: '', sending: false, error: '' });
  const [loadingHistory, setLoadingHistory] = createSignal(false);
  const [historyExhausted, setHistoryExhausted] = createSignal(false);

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
    feed.stream_events.filter((e) =>
      settings.streams_filters[e.src] !== false
      && !isProjectTraceNoise(e)
      && !isDialogAgentStep(e)
    );

  function formatHistoryEvent(ev) {
    const payload = ev.payload || {};
    let body = '';
    if (ev.kind === 'internal.thought' && payload.text) {
      body = `"${payload.text}"`;
    } else if (ev.text) {
      body = ev.text;
    } else if (payload.tool) {
      body = `tool=${payload.tool} ${payload.arg ? '· ' + String(payload.arg).slice(0, 100) : ''}`;
    } else if (payload.summary) {
      body = payload.summary;
    } else if (ev.kind?.startsWith('provider.') && payload.provider_id) {
      body = `provider=${payload.provider_id} status=${payload.status || ''}`.trim();
    } else if (payload.next_step) {
      body = `next: ${payload.next_step}`;
    } else if (ev.kind?.startsWith('subagent.') || ev.kind?.startsWith('project.')) {
      body = '';
    } else if (!ev.kind?.startsWith('internal.scheduler')) {
      try { body = JSON.stringify(payload).slice(0, 150); } catch { body = ''; }
    }
    return {
      seq: ev.seq,
      ts: ev.ts ? new Date(ev.ts).toLocaleTimeString('ru-RU', { hour12: false }) : '',
      kind: ev.kind,
      src: ev.src || 'system',
      channel: ev.channel || '',
      session_id: ev.session_id,
      body,
    };
  }

  async function loadOlderEvents() {
    if (loadingHistory() || historyExhausted()) return;
    const oldestSeq = feed.stream_events.reduce((min, ev) => {
      const seq = typeof ev.seq === 'number' ? ev.seq : null;
      if (seq == null) return min;
      return min == null || seq < min ? seq : min;
    }, null);
    setLoadingHistory(true);
    try {
      const r = await loadEventHistory(oldestSeq || 0, 80);
      prependStreamEvents((r.events || [])
        .filter((ev) => !isProjectTraceNoise(ev) && !isDialogAgentStep(ev))
        .map(formatHistoryEvent));
      if (!r.has_more) setHistoryExhausted(true);
    } finally {
      setLoadingHistory(false);
    }
  }

  function onScroll(e) {
    if (e.currentTarget.scrollTop < 60) loadOlderEvents();
  }

  onMount(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') props.onClose?.();
    };
    window.addEventListener('keydown', onKey);
    onCleanup(() => window.removeEventListener('keydown', onKey));
    loadOlderEvents();
  });

  return (
    <div class="streams-backdrop" onClick={() => props.onClose?.()}>
      <section
        classList={{
          streams: true,
          collapsed: settings.streams_collapsed,
        }}
        onClick={(event) => event.stopPropagation()}
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
        <button class="streams-close" onClick={(e) => { e.stopPropagation(); props.onClose?.(); }}>×</button>
        <span class="toggle">⌃</span>
      </div>

      <div class="streams-body" onScroll={onScroll}>
        <div class="inner-debug-summary">
          <div class="inner-debug-title">inner diagnostics</div>
          <div class="inner-debug-grid">
            <div><span>private/hour</span><b>{feed.private_count_last_hour}</b></div>
            <For each={DRIVE_ORDER}>
              {(key) => <div><span>{key}</span><b>{(feed.drives[key] ?? 0).toFixed(2)}</b></div>}
            </For>
          </div>
        </div>
        <Show when={feed.inner_thoughts.length > 0}>
          <div class="inner-thought-list">
            <For each={feed.inner_thoughts.slice(0, 8)}>
              {(t) => (
                <div classList={{ 'inner-thought-row': true, private: t.private }}>
                  <span>{t.age}</span>
                  <p>{t.private ? '(private thought hidden)' : t.text}</p>
                </div>
              )}
            </For>
          </div>
        </Show>
        <Show when={loadingHistory()}>
          <div class="history-loader">loading older logs...</div>
        </Show>
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
    </div>
  );
}
