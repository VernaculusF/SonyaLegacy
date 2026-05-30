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
  let timer;

  async function refresh() {
    try {
      const s = await api.getSnapshot();
      setSnap(s);
      const live = await api.getLiveSteps(sinceSeq, 40);
      if (live.events && live.events.length) {
        sinceSeq = live.events[live.events.length - 1].seq;
        setSteps((cur) => [...cur, ...live.events].slice(-120));
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

      <div class="live-steps">
        <For each={steps().slice().reverse()}>
          {(ev) => (
            <div class="step-row">
              <span class="step-seq">{ev.seq}</span>
              <span class="step-kind">{ev.kind?.replace('internal.', '')}</span>
              <span class="step-data">{ev.data?.tool ? `${ev.data.tool} ${(ev.data.arg || '').slice(0, 80)}` : (ev.data?.chosen_kind || ev.data?.thought || JSON.stringify(ev.data || {}).slice(0, 90))}</span>
            </div>
          )}
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
  return (
    <div class="panel">
      <div class="panel-head"><h3>TASKS ({tasks().length})</h3>
        <button class="btn ghost" onClick={refresh}>обновить</button></div>
      <div class="card-list">
        <For each={tasks()} fallback={<div class="muted">нет задач</div>}>
          {(t) => (
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
                <button class="chip-btn" onClick={() => api.taskAction(t.task_id, 'unblock').then(refresh).catch((e)=>props.onErr(e.message))}>unblock</button>
                <button class="chip-btn" onClick={() => api.taskAction(t.task_id, 'fail').then(refresh).catch((e)=>props.onErr(e.message))}>fail</button>
                <button class="chip-btn danger" onClick={() => confirm('удалить задачу?') && api.deleteTask(t.task_id).then(refresh).catch((e)=>props.onErr(e.message))}>delete</button>
              </div>
            </div>
          )}
        </For>
      </div>
    </div>
  );
}

// ---------------- Selfmod ----------------
function SelfmodPanel(props) {
  const [props_, setProps] = createSignal([]);
  async function refresh() {
    try { const r = await api.getSelfmodList(); setProps(r.proposals || []); }
    catch (e) { props.onErr('selfmod: ' + e.message); }
  }
  onMount(refresh);
  return (
    <div class="panel">
      <div class="panel-head"><h3>SELFMOD ({props_().length})</h3>
        <button class="btn ghost" onClick={refresh}>обновить</button></div>
      <div class="card-list">
        <For each={props_()} fallback={<div class="muted">нет предложений</div>}>
          {(p) => (
            <div class="card">
              <div class="card-top">
                <span classList={{ badge: true, [p.status]: true }}>{p.status}</span>
                <span class="card-title mono">{p.target_module}</span>
              </div>
              <div class="card-desc">{p.summary}</div>
              <div class="card-actions">
                <button class="chip-btn ok" onClick={() => api.approveSelfmod(p.proposal_id).then(refresh).catch((e)=>props.onErr(e.message))}>approve</button>
                <button class="chip-btn danger" onClick={() => api.denySelfmod(p.proposal_id).then(refresh).catch((e)=>props.onErr(e.message))}>deny</button>
              </div>
            </div>
          )}
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
  async function refresh() {
    try { const r = await api.getProviders(); setKeys(r.keys || []); setSettings(r.settings || {}); }
    catch (e) { props.onErr('providers: ' + e.message); }
  }
  onMount(refresh);
  return (
    <div class="panel">
      <div class="panel-head"><h3>PROVIDERS ({keys().length})</h3>
        <div class="panel-actions">
          <button class="btn ghost" onClick={() => api.refreshBalance().then(refresh).catch((e)=>props.onErr(e.message))}>refresh balance</button>
          <button class="btn ghost" onClick={refresh}>обновить</button>
        </div>
      </div>
      <div class="muted small">active: {settings_().active_provider} · {settings_().default_model}</div>
      <div class="card-list">
        <For each={keys()} fallback={<div class="muted">нет ключей</div>}>
          {(k) => (
            <div class="card">
              <div class="card-top">
                <span classList={{ badge: true, [k.status]: true }}>{k.status}</span>
                <span class="card-title">{k.name}</span>
                <span class="spacer"></span>
                <span class="muted small mono">{k.provider}</span>
              </div>
              <div class="card-desc mono small">{k.key_masked} · req {k.request_count} · err {k.error_count}{k.balance != null ? ` · $${k.balance}` : ''}</div>
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
