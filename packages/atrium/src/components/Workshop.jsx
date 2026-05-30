/* Workshop — обзор Сониного «кода жизни». ТОЛЬКО ПРОСМОТР СПИСКА.
 *
 *   - skills    : Python в src/sonya/skills/builtins/*.py
 *   - tools     : tools/*.py + plugins/*.py
 *   - packages  : packages/* (atrium, tg-userbot)
 *
 * Никакого чтения содержимого / редактирования из Atrium — изменения через
 * git как обычный код. Здесь Иван видит только ЧТО у неё есть (список).
 *
 * Открывается из header («⚙ workshop») как полноэкранный overlay.
 */
import { createSignal, onMount, onCleanup, For, Show } from 'solid-js';
import { settings } from '../store.js';

const KINDS = [
  { id: 'skills', label: 'skills', desc: 'Python поведение (skills.run) — список' },
  { id: 'tools', label: 'tools', desc: 'тулы — список' },
  { id: 'packages', label: 'packages', desc: 'подпроекты — список' },
];

async function api(path, opts = {}) {
  const url = `http://${settings.vps_host}${path}`;
  const headers = {
    'X-Atrium-Token': settings.atrium_token,
    ...(opts.headers || {}),
  };
  const r = await fetch(url, { ...opts, headers });
  const text = await r.text();
  let json;
  try { json = JSON.parse(text); } catch { json = { error: text }; }
  if (!r.ok) throw new Error(json.error || `HTTP ${r.status}`);
  return json;
}

export default function Workshop(props) {
  const [kind, setKind] = createSignal('skills');
  const [items, setItems] = createSignal([]);
  const [busy, setBusy] = createSignal(false);
  const [status, setStatus] = createSignal('');

  function _countFiles(nodes) {
    let n = 0;
    for (const it of nodes || []) {
      if (it && it.type === 'dir') n += _countFiles(it.children);
      else n += 1;
    }
    return n;
  }
  const listCount = () => {
    if (kind() === 'packages') {
      const pkgs = items().length;
      const files = _countFiles(items());
      return `${pkgs} pkg · ${files} files`;
    }
    return items().length;
  };

  async function loadList() {
    setBusy(true);
    setStatus('');
    try {
      const r = await api(`/api/atrium/workshop/list?kind=${kind()}`);
      setItems(r.items || []);
    } catch (e) {
      setStatus('list failed: ' + e.message);
      setItems([]);
    } finally {
      setBusy(false);
    }
  }

  onMount(() => {
    loadList();
    const onKey = (e) => {
      if (e.key === 'Escape') props.onClose?.();
    };
    window.addEventListener('keydown', onKey);
    onCleanup(() => window.removeEventListener('keydown', onKey));
  });

  /** Read-only строка списка. Клик ничего не делает. */
  function ListRow(p) {
    return (
      <div class="ws-item readonly" title={`${p.item.path || p.item.name}${p.meta ? ' · ' + p.meta : ''}`}>
        <span class="ws-item-name">{p.item.path || p.item.name}</span>
        <span class="ws-item-size">{p.meta}</span>
      </div>
    );
  }

  return (
    <div class="workshop-overlay">
      <div class="workshop">
        <div class="workshop-header">
          <span class="logo">⚙ WORKSHOP</span>
          <div class="kind-tabs">
            <For each={KINDS}>
              {(k) => (
                <button
                  classList={{ tab: true, on: kind() === k.id }}
                  onClick={() => { setKind(k.id); loadList(); }}
                  title={k.desc}
                >{k.label}</button>
              )}
            </For>
          </div>
          <span class="spacer"></span>
          <span class="status">{status()}</span>
          <span class="exit" onClick={() => props.onClose?.()} title="закрыть (Esc)">⏏</span>
        </div>

        <div class="workshop-body single">
          <aside class="ws-list wide">
            <div class="ws-list-head">
              <span>{kind()} ({listCount()})</span>
              <span class="ws-readonly-tag">read-only</span>
            </div>
            <div class="ws-list-scroll">
              <Show when={!busy()} fallback={<div class="ws-empty">загрузка…</div>}>
                <Show when={items().length > 0} fallback={<div class="ws-empty">пусто</div>}>
                  <Show
                    when={kind() === 'packages'}
                    fallback={
                      <For each={items()}>
                        {(it) => <ListRow item={it} meta={`${Math.round(it.size / 102.4) / 10}k`} />}
                      </For>
                    }
                  >
                    <For each={items()}>
                      {(pkg) => (
                        <ListRow
                          item={{ path: pkg.name, name: pkg.name }}
                          meta={`${_countFiles(pkg.children)} files`}
                        />
                      )}
                    </For>
                  </Show>
                </Show>
              </Show>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
