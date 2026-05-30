/* Console — Atrium's built-in operator panel. Mirrors the admin web UI so
 * Ivan manages Sonya entirely from the desktop app (the admin panel stays as
 * a VPS fallback). Sections: Operator · Tasks · Selfmod · Approvals ·
 * Providers · Core · Substrate · Repo.
 *
 * Each section polls/loads on demand. Auth via X-Atrium-Token (consoleApi).
 */
import { createSignal, onMount, onCleanup, For, Show } from 'solid-js';
import * as api from '../consoleApi.js';

const SECTIONS = [
  { id: 'operator', label: 'operator' },
  { id: 'tasks', label: 'tasks' },
  { id: 'selfmod', label: 'selfmod' },
  { id: 'approvals', label: 'approvals' },
  { id: 'providers', label: 'providers' },
  { id: 'core', label: 'core' },
  { id: 'substrate', label: 'substrate' },
  { id: 'repo', label: 'repo' },
];

export default function Console(props) {
  const [section, setSection] = createSignal('operator');
  const [err, setErr] = createSignal('');

  onMount(() => {
    const onKey = (e) => { if (e.key === 'Escape') props.onClose?.(); };
    window.addEventListener('keydown', onKey);
    onCleanup(() => window.removeEventListener('keydown', onKey));
  });

  return (
    <div class="console-overlay">
      <div class="console">
        <aside class="console-nav">
          <div class="console-brand">CONSOLE</div>
          <For each={SECTIONS}>
            {(s) => (
              <button
                classList={{ 'console-nav-item': true, on: section() === s.id }}
                onClick={() => { setErr(''); setSection(s.id); }}
              >{s.label}</button>
            )}
          </For>
          <span class="console-nav-spacer"></span>
          <button class="console-close" onClick={() => props.onClose?.()}>✕ закрыть</button>
        </aside>
        <main class="console-body">
          <Show when={err()}><div class="console-err">{err()}</div></Show>
          <Show when={section() === 'operator'}><OperatorPanel onErr={setErr} /></Show>
          <Show when={section() === 'tasks'}><TasksPanel onErr={setErr} /></Show>
          <Show when={section() === 'selfmod'}><SelfmodPanel onErr={setErr} /></Show>
          <Show when={section() === 'approvals'}><ApprovalsPanel onErr={setErr} /></Show>
          <Show when={section() === 'providers'}><ProvidersPanel onErr={setErr} /></Show>
          <Show when={section() === 'core'}><CorePanel onErr={setErr} /></Show>
          <Show when={section() === 'substrate'}><SubstratePanel onErr={setErr} /></Show>
          <Show when={section() === 'repo'}><RepoPanel onErr={setErr} /></Show>
        </main>
      </div>
    </div>
  );
}

// ---------------- Operator ----------------
function OperatorPanel(props) {
  const [snap, setSnap] = createSignal(null);
  const [steps, setSteps] = createSignal([]);
  const [inject, setInject] = createSignal('');
  let sinceSeq = 0;
  let initialized = false;
  let timer;
  let logEl;

  // Persist sinceSeq across Console open/close so we don't restart from scratch.
  const _SINCE_KEY = 'atrium.console.operator.since';

  async function refresh() {
    try {
      const s = await api.getSnapshot();
      setSnap(s);
      // First call: anchor to recent tail (last 30 events) unless we have a
      // saved sinceSeq from a prior session.
      if (!initialized) {
        const saved = parseInt(sessionStorage.getItem(_SINCE_KEY) || '0', 10);
        if (saved > 0 && s && s.latest_seq && saved < s.latest_seq + 100) {
          sinceSeq = saved;
        } else {
          sinceSeq = (s && s.latest_seq) ? Math.max(0, s.latest_seq - 30) : 0;
        }
        initialized = true;
      }
      const live = await api.getLiveSteps(sinceSeq, 80);
      if (live.events && live.events.length) {
        sinceSeq = live.events[live.events.length - 1].seq;
        sessionStorage.setItem(_SINCE_KEY, String(sinceSeq));
        // Detect "user is near bottom" so we only auto-scroll then.
        let nearBottom = true;
        if (logEl) {
          nearBottom = (logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight) < 80;
        }
        setSteps((cur) => [...cur, ...live.events].slice(-300));
        if (nearBottom) {
          queueMicrotask(() => {
            if (logEl) logEl.scrollTop = logEl.scrollHeight;
          });
        }
      }
    } catch (e) { props.onErr('operator: ' + e.message); }
  }
  onMount(() => { refresh(); timer = setInterval(refresh, 3000); });
  onCleanup(() => clearInterval(timer));

  return (
    <div class="panel">
      <div class="panel-head">
        <h3>OPERATOR</h3>
        <div class="panel-actions">
          <button class="btn" onClick={() => api.triggerActive().then(refresh).catch((e) => props.onErr(e.message))}>
            ⚡ разбудить сессию
          </button>
        </div>
      </div>

      <Show when={snap()}>
        <div class="stat-grid">
          <div class="stat"><span class="stat-k">latest seq</span><span class="stat-v">{snap().latest_seq}</span></div>
          <div class="stat"><span class="stat-k">active</span><span class="stat-v">{snap().active_session?.current_tool || '—'}</span></div>
          <div class="stat"><span class="stat-k">tasks in progress</span><span class="stat-v">{snap().open_tasks_summary?.in_progress ?? 0}</span></div>
          <div class="stat"><span class="stat-k">approved selfmod</span><span class="stat-v">{snap().approved_proposals_pending ?? 0}</span></div>
        </div>
      </Show>

      <div class="inject-row">
        <input
          type="text"
          placeholder="инжектнуть сообщение как будто от Ивана…"
          value={inject()}
          onInput={(e) => setInject(e.currentTarget.value)}
        />
        <button class="btn" onClick={() => {
          const t = inject().trim(); if (!t) return;
          api.injectMessage(t).then(() => setInject('')).catch((e) => props.onErr(e.message));
        }}>inject</button>
      </div>

      <div class="live-steps" ref={(el) => (logEl = el)}>
        <For each={steps()} fallback={<div class="muted small">ждём событий…</div>}>
          {(ev) => {
            const k = (ev.kind || '').replace('internal.', '').replace('outgoing.', '→ ').replace('incoming.', '← ').replace('self_mod.', 'selfmod.');
            const d = ev.data || {};
            let body = '';
            if (d.tool) body = `${d.tool}${d.arg ? ' · ' + d.arg : ''}`;
            else if (d.chosen_kind) body = `${d.chosen_kind}/${d.chosen_reason}`;
            else if (d.text) body = d.text;
            else if (d.task_id) body = `${d.task_id}${d.status ? ' · ' + d.status : ''}`;
            else if (d.preview) body = d.preview;
            else if (d.thought) body = d.thought;
            else body = '';
            return (
              <div classList={{ 'step-row': true, 'kind-step': ev.kind === 'internal.agent_step', 'kind-blocker': ev.kind === 'internal.blocker_detected' }}>
                <span class="step-seq">{ev.seq}</span>
                <span class="step-kind">{k}</span>
                <span class="step-data">{body}</span>
              </div>
            );
          }}
        </For>
      </div>
    </div>
  );
}

// ---------------- Tasks ----------------
function TasksPanel(props) {
  const [tasks, setTasks] = createSignal([]);
  async function refresh() {
    try { const r = await api.getTasks(); setTasks(r.tasks || []); }
    catch (e) { props.onErr('tasks: ' + e.message); }
  }
  onMount(refresh);

  function _act(taskId, action, confirmMsg) {
    if (confirmMsg && !confirm(confirmMsg)) return;
    api.taskAction(taskId, action).then(refresh).catch((e)=>props.onErr(e.message));
  }

  return (
    <div class="panel">
      <div class="panel-head"><h3>TASKS ({tasks().length})</h3>
        <button class="btn ghost" onClick={refresh}>обновить</button></div>
      <div class="card-list">
        <For each={tasks()} fallback={<div class="muted">нет задач</div>}>
          {(t) => {
            const isOpen = ['pending', 'in_progress', 'blocked', 'paused'].includes(t.status);
            const canPause = t.status === 'in_progress' || t.status === 'pending';
            const canResume = t.status === 'paused';
            const canUnblock = t.status === 'blocked';
            const canFail = isOpen;
            const canRepurpose = t.status === 'failed' || t.status === 'done';
            return (
              <div class="card">
                <div class="card-top">
                  <span classList={{ badge: true, [t.status]: true }}>{t.status}</span>
                  <span class="card-title">{t.title}</span>
                  <span class="spacer"></span>
                  <span class="muted">{t.completed_count}/{t.total_steps}</span>
                </div>
                <Show when={t.description}><div class="card-desc">{t.description}</div></Show>
                <Show when={t.next_step_hint}><div class="card-hint">→ {t.next_step_hint}</div></Show>
                <div class="card-actions">
                  <Show when={canPause}>
                    <button class="chip-btn" onClick={() => _act(t.task_id, 'pause')}>pause</button>
                  </Show>
                  <Show when={canResume}>
                    <button class="chip-btn ok" onClick={() => _act(t.task_id, 'resume')}>resume</button>
                  </Show>
                  <Show when={canUnblock}>
                    <button class="chip-btn" onClick={() => _act(t.task_id, 'unblock')}>unblock</button>
                  </Show>
                  <Show when={canFail}>
                    <button class="chip-btn danger" onClick={() => _act(t.task_id, 'fail', 'отметить как failed?')}>fail</button>
                  </Show>
                  <Show when={canRepurpose}>
                    <button class="chip-btn" onClick={() => _act(t.task_id, 'repurpose', 'сбросить и начать заново?')}>repurpose</button>
                  </Show>
                  <button class="chip-btn danger" onClick={() => confirm('удалить задачу?') && api.deleteTask(t.task_id).then(refresh).catch((e)=>props.onErr(e.message))}>delete</button>
                </div>
              </div>
            );
          }}
        </For>
      </div>
    </div>
  );
}

// ---------------- Selfmod ----------------
// Action visibility:
//   - PROPOSED / VALIDATING / PASSED_LAYER_*: she's still validating it. Approve/deny don't apply.
//   - REQUIRES_GOVERNED_CHANGE: this is what needs Ivan's decision. show approve/deny.
//   - GOVERNED_APPROVED / APPROVED: already accepted, waiting for apply. read-only.
//   - REJECTED / APPLIED / REVERTED: terminal. read-only.
const SELFMOD_NEEDS_DECISION = new Set(['requires_governed_change']);

function SelfmodPanel(props) {
  const [items, setItems] = createSignal([]);
  const [filter, setFilter] = createSignal('needs_decision'); // needs_decision | all

  async function refresh() {
    try { const r = await api.getSelfmodList(); setItems(r.proposals || []); }
    catch (e) { props.onErr('selfmod: ' + e.message); }
  }
  onMount(refresh);

  const visible = () => {
    const all = items();
    if (filter() === 'all') return all;
    return all.filter((p) => SELFMOD_NEEDS_DECISION.has(p.status));
  };

  return (
    <div class="panel">
      <div class="panel-head">
        <h3>SELFMOD ({visible().length}{filter() === 'needs_decision' && items().length > visible().length ? ` / ${items().length}` : ''})</h3>
        <div class="panel-actions">
          <button classList={{ 'chip-btn': true, on: filter() === 'needs_decision' }} onClick={() => setFilter('needs_decision')}>требуют решения</button>
          <button classList={{ 'chip-btn': true, on: filter() === 'all' }} onClick={() => setFilter('all')}>все</button>
          <button class="btn ghost" onClick={refresh}>обновить</button>
        </div>
      </div>
      <div class="card-list">
        <For each={visible()} fallback={<div class="muted">{filter() === 'needs_decision' ? 'нет предложений ждущих твоего решения. для governed-changes Соня сама проходит pipeline; здесь появляются только critical-path proposals (требующие одобрения primary anchor).' : 'нет предложений'}</div>}>
          {(p) => {
            const needsDecision = SELFMOD_NEEDS_DECISION.has(p.status);
            return (
              <div class="card">
                <div class="card-top">
                  <span classList={{ badge: true, [p.status]: true }}>{p.status.replace(/_/g, ' ')}</span>
                  <span class="card-title mono">{p.target_module}</span>
                </div>
                <div class="card-desc">{p.summary}</div>
                <Show when={needsDecision}>
                  <div class="card-actions">
                    <button class="chip-btn ok" onClick={() => api.approveSelfmod(p.proposal_id).then(refresh).catch((e)=>props.onErr(e.message))}>approve</button>
                    <button class="chip-btn danger" onClick={() => api.denySelfmod(p.proposal_id).then(refresh).catch((e)=>props.onErr(e.message))}>deny</button>
                  </div>
                </Show>
              </div>
            );
          }}
        </For>
      </div>
    </div>
  );
}

// ---------------- Approvals ----------------
function ApprovalsPanel(props) {
  const [reqs, setReqs] = createSignal([]);
  async function refresh() {
    try { const r = await api.getApprovals(); setReqs(r.requests || []); }
    catch (e) { props.onErr('approvals: ' + e.message); }
  }
  onMount(refresh);
  return (
    <div class="panel">
      <div class="panel-head"><h3>APPROVALS ({reqs().length})</h3>
        <button class="btn ghost" onClick={refresh}>обновить</button></div>
      <div class="card-list">
        <For each={reqs()} fallback={<div class="muted">нет запросов</div>}>
          {(r) => (
            <div class="card">
              <div class="card-top">
                <span classList={{ badge: true, [r.status]: true }}>{r.status}</span>
                <span class="card-title mono">{r.action}</span>
              </div>
              <div class="card-desc mono">{r.scope}</div>
              <Show when={r.status === 'pending'}>
                <div class="card-actions">
                  <button class="chip-btn ok" onClick={() => api.decideApproval(r.request_id, 'approve').then(refresh).catch((e)=>props.onErr(e.message))}>approve</button>
                  <button class="chip-btn danger" onClick={() => api.decideApproval(r.request_id, 'deny').then(refresh).catch((e)=>props.onErr(e.message))}>deny</button>
                </div>
              </Show>
            </div>
          )}
        </For>
      </div>
    </div>
  );
}

// ---------------- Providers ----------------
function ProvidersPanel(props) {
  const [keys, setKeys] = createSignal([]);
  const [settings_, setSettings] = createSignal({});
  const [editing, setEditing] = createSignal(false);
  const [draft, setDraft] = createSignal({});
  async function refresh() {
    try {
      const r = await api.getProviders();
      setKeys(r.keys || []);
      setSettings(r.settings || {});
      setDraft({
        active_provider: r.settings?.active_provider || '',
        default_model: r.settings?.default_model || '',
        default_base_url: r.settings?.default_base_url || '',
      });
    }
    catch (e) { props.onErr('providers: ' + e.message); }
  }
  onMount(refresh);

  async function saveSettings() {
    try {
      await api.setProviderSettings(draft());
      setEditing(false);
      await refresh();
    } catch (e) { props.onErr(e.message); }
  }

  return (
    <div class="panel">
      <div class="panel-head"><h3>PROVIDERS ({keys().length})</h3>
        <div class="panel-actions">
          <button class="btn ghost" onClick={() => api.refreshBalance().then(refresh).catch((e)=>props.onErr(e.message))}>refresh balance</button>
          <button class="btn ghost" onClick={refresh}>обновить</button>
        </div>
      </div>

      <div class="card">
        <div class="card-top">
          <span class="card-title">defaults</span>
          <span class="spacer"></span>
          <Show when={!editing()}>
            <button class="chip-btn" onClick={() => setEditing(true)}>edit</button>
          </Show>
          <Show when={editing()}>
            <button class="chip-btn ok" onClick={saveSettings}>save</button>
            <button class="chip-btn" onClick={() => { setEditing(false); refresh(); }}>cancel</button>
          </Show>
        </div>
        <Show when={!editing()}>
          <div class="kv-grid">
            <div><span class="kv-k">active</span><span class="kv-v mono">{settings_().active_provider || '—'}</span></div>
            <div><span class="kv-k">model</span><span class="kv-v mono">{settings_().default_model || '—'}</span></div>
            <div><span class="kv-k">base url</span><span class="kv-v mono small">{settings_().default_base_url || '—'}</span></div>
          </div>
        </Show>
        <Show when={editing()}>
          <div class="form-grid">
            <label>active provider
              <input type="text" value={draft().active_provider}
                onInput={(e) => setDraft({ ...draft(), active_provider: e.currentTarget.value })} />
            </label>
            <label>default model
              <input type="text" value={draft().default_model}
                onInput={(e) => setDraft({ ...draft(), default_model: e.currentTarget.value })} />
            </label>
            <label>default base url
              <input type="text" value={draft().default_base_url}
                onInput={(e) => setDraft({ ...draft(), default_base_url: e.currentTarget.value })} />
            </label>
          </div>
        </Show>
      </div>

      <div class="card-list">
        <For each={keys()} fallback={<div class="muted">нет ключей</div>}>
          {(k) => (
            <div class="card">
              <div class="card-top">
                <span classList={{ badge: true, [k.status]: true }}>{k.status}</span>
                <span class="card-title">{k.name}</span>
                <span class="muted small">slot: {k.slot || '—'}</span>
                <span class="spacer"></span>
                <span class="muted small mono">{k.provider}</span>
              </div>
              <div class="card-desc mono small">{k.key_masked} · req {k.request_count} · err {k.error_count}{k.balance != null ? ` · $${k.balance}` : ''}</div>
              <Show when={k.model}>
                <div class="muted small mono">model: {k.model}</div>
              </Show>
              <div class="card-actions">
                <button class="chip-btn" onClick={() => api.testProviderKey(k.key_id).then((r)=>props.onErr(r.ok?`✓ ${k.name} ok`:`✗ ${r.error}`)).catch((e)=>props.onErr(e.message))}>test</button>
                <button class="chip-btn" onClick={() => api.setProviderKeyStatus(k.key_id, k.status === 'active' ? 'disabled' : 'active').then(refresh).catch((e)=>props.onErr(e.message))}>{k.status === 'active' ? 'disable' : 'enable'}</button>
              </div>
            </div>
          )}
        </For>
      </div>
    </div>
  );
}

// ---------------- Core ----------------
function CorePanel(props) {
  const [status, setStatus] = createSignal(null);
  const [logs, setLogs] = createSignal('');
  async function refresh() {
    try { setStatus(await api.getCoreStatus()); setLogs((await api.getCoreLogs(120)).logs || ''); }
    catch (e) { props.onErr('core: ' + e.message); }
  }
  onMount(refresh);
  return (
    <div class="panel">
      <div class="panel-head"><h3>CORE</h3>
        <button class="btn ghost" onClick={refresh}>обновить</button></div>
      <Show when={status()}>
        <div class="stat-grid">
          <div class="stat"><span class="stat-k">running</span><span classList={{ 'stat-v': true, ok: status().running, warn: !status().running }}>{status().running ? 'да' : 'нет'}</span></div>
          <div class="stat"><span class="stat-k">pid</span><span class="stat-v">{status().pid || '—'}</span></div>
        </div>
      </Show>
      <div class="panel-actions">
        <button class="btn" onClick={() => api.startCore('full').then(refresh).catch((e)=>props.onErr(e.message))}>start</button>
        <button class="btn danger" onClick={() => confirm('остановить ядро?') && api.stopCore().then(refresh).catch((e)=>props.onErr(e.message))}>stop</button>
      </div>
      <pre class="log-view">{logs() || 'нет логов'}</pre>
    </div>
  );
}

// ---------------- Substrate ----------------
function SubstratePanel(props) {
  const [data, setData] = createSignal(null);
  async function refresh() {
    try { setData(await api.getSubstrate()); }
    catch (e) { props.onErr('substrate: ' + e.message); }
  }
  onMount(refresh);
  return (
    <div class="panel">
      <div class="panel-head"><h3>SUBSTRATE</h3>
        <button class="btn ghost" onClick={refresh}>обновить</button></div>
      <Show when={data()}>
        <div class="muted small mono">v{data().version} · {data().path}</div>
        <div class="table">
          <For each={data().tables || []}>
            {(t) => (
              <div class="table-row">
                <span class="mono">{t.name}</span>
                <span class="spacer"></span>
                <span class="muted">{t.rows}</span>
              </div>
            )}
          </For>
        </div>
      </Show>
    </div>
  );
}

// ---------------- Repo ----------------
function RepoPanel(props) {
  const [st, setSt] = createSignal(null);
  const [busy, setBusy] = createSignal(false);
  const [msg, setMsg] = createSignal('');
  const [note, setNote] = createSignal('');

  async function refresh() {
    setBusy(true);
    try { setSt(await api.getRepoStatus()); }
    catch (e) { props.onErr('repo: ' + e.message); }
    finally { setBusy(false); }
  }
  onMount(refresh);

  async function doAct(fn, label) {
    setBusy(true); setNote('');
    try { const r = await fn(); setNote(`✓ ${label}: ${JSON.stringify(r).slice(0, 160)}`); await refresh(); }
    catch (e) { props.onErr(`${label}: ${e.message}`); }
    finally { setBusy(false); }
  }

  return (
    <div class="panel">
      <div class="panel-head"><h3>REPO (VPS)</h3>
        <button class="btn ghost" disabled={busy()} onClick={refresh}>обновить</button></div>
      <Show when={st()}>
        <div class="stat-grid">
          <div class="stat"><span class="stat-k">branch</span><span class="stat-v mono">{st().branch}</span></div>
          <div class="stat"><span class="stat-k">ahead</span><span class="stat-v">{st().ahead}</span></div>
          <div class="stat"><span class="stat-k">behind</span><span class="stat-v">{st().behind}</span></div>
          <div class="stat"><span class="stat-k">грязных</span><span classList={{ 'stat-v': true, warn: st().dirty_count > 0 }}>{st().dirty_count}</span></div>
        </div>
        <Show when={st().dirty && st().dirty.length}>
          <pre class="log-view small">{st().dirty.join('\n')}</pre>
        </Show>
        <div class="commit-row">
          <input type="text" placeholder="commit message…" value={msg()} onInput={(e) => setMsg(e.currentTarget.value)} />
          <button class="btn" disabled={busy() || !msg().trim()} onClick={() => doAct(() => api.repoCommit(msg()).then((r) => { setMsg(''); return r; }), 'commit')}>commit</button>
          <button class="btn" disabled={busy()} onClick={() => doAct(api.repoPush, 'push')}>push</button>
        </div>
        <div class="panel-actions">
          <button class="btn ghost" disabled={busy()} onClick={() => confirm('сбросить НЕзакоммиченные изменения?') && doAct(() => api.repoRevert('discard'), 'discard')}>discard local</button>
          <button class="btn danger" disabled={busy()} onClick={() => confirm('hard reset к origin? (потеряются локальные коммиты)') && doAct(() => api.repoRevert('reset_to_origin'), 'reset→origin')}>reset → origin</button>
        </div>
        <div class="repo-log">
          <For each={st().log || []}>{(l) => <div class="repo-log-line mono">{l}</div>}</For>
        </div>
      </Show>
      <Show when={note()}><div class="console-note">{note()}</div></Show>
    </div>
  );
}
