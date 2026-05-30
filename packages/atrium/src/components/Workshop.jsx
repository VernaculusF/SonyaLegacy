/* Workshop — Сонин «код жизни».
 *
 *   - skills    : Python в src/sonya/skills/builtins/*.py
 *                 → ПОЛНЫЙ доступ: смотреть, редактировать, создавать новые,
 *                   спрашивать Соню про файл (reply).
 *   - tools     : tools/*.py + plugins/*.py
 *                 → ТОЛЬКО список (имя + размер). Чтение/редактирование запрещено.
 *   - packages  : packages/* (atrium, tg-userbot)
 *                 → ТОЛЬКО список верхнеуровневых пакетов (имя + кол-во файлов).
 *                   Никаких раскрытий, чтения, редактирования.
 *
 * Открывается из header («⚙ workshop») как полноэкранный overlay.
 */
import { createSignal, onMount, onCleanup, For, Show } from 'solid-js';
import { settings } from '../store.js';

const KINDS = [
  { id: 'skills', label: 'skills', desc: 'Python поведение (skills.run)' },
  { id: 'tools', label: 'tools', desc: 'тулы (read-only список)' },
  { id: 'packages', label: 'packages', desc: 'подпроекты (read-only список)' },
];

const EDITABLE_KINDS = new Set(['skills']);

async function api(path, opts = {}) {
  const url = `http://${settings.vps_host}${path}`;
  const headers = {
    'X-Atrium-Token': settings.atrium_token,
    ...(opts.headers || {}),
  };
  if (opts.body && typeof opts.body === 'object') {
    opts.body = JSON.stringify(opts.body);
    headers['Content-Type'] = 'application/json';
  }
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
  const [active, setActive] = createSignal(null);
  const [content, setContent] = createSignal('');
  const [savedContent, setSavedContent] = createSignal('');
  const [busy, setBusy] = createSignal(false);
  const [status, setStatus] = createSignal('');
  const [replyMsg, setReplyMsg] = createSignal('');
  const dirty = () => content() !== savedContent();
  const editable = () => EDITABLE_KINDS.has(kind());

  // Recursive file count for tree (packages).
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
    setActive(null);
    setContent('');
    setSavedContent('');
    try {
      const r = await api(`/api/atrium/workshop/list?kind=${kind()}`);
      setItems(r.items || []);
    } catch (e) {
      setStatus('list failed: ' + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function openFile(it) {
    if (!editable()) return;  // tools/packages — read-only список
    if (dirty() && !confirm('есть несохранённые изменения. сбросить?')) return;
    setBusy(true);
    setStatus('');
    try {
      const r = await api(`/api/atrium/workshop/read?kind=${kind()}&path=${encodeURIComponent(it.path)}`);
      setActive({ ...it, lang: r.lang });
      setContent(r.content || '');
      setSavedContent(r.content || '');
    } catch (e) {
      setStatus('read failed: ' + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!active() || !editable()) return;
    setBusy(true);
    setStatus('');
    try {
      await api('/api/atrium/workshop/write', {
        method: 'POST',
        body: { kind: kind(), path: active().path, content: content() },
      });
      setSavedContent(content());
      setStatus(`saved → ${active().path}`);
      loadList();
    } catch (e) {
      setStatus('save failed: ' + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function newFile() {
    if (!editable()) return;
    if (dirty() && !confirm('есть несохранённые изменения. сбросить?')) return;
    const name = prompt('имя файла (например: my_helper.py):');
    if (!name || !/^[a-z0-9_]+\.py$/i.test(name)) {
      setStatus('only .py with [a-z0-9_]');
      return;
    }
    const stub = `"""${name} — skill module."""\n\ndef run(ctx) -> str:\n    return "TODO"\n`;
    setActive({ path: name, name, lang: 'python', size: stub.length });
    setContent(stub);
    setSavedContent('');
    setStatus('new (unsaved) — Ctrl+S чтобы сохранить');
  }

  async function sendReply() {
    if (!replyMsg().trim() || !editable()) return;
    setBusy(true);
    setStatus('');
    try {
      await api('/api/atrium/workshop/reply', {
        method: 'POST',
        body: {
          kind: kind(),
          path: active() ? active().path : '',
          message: replyMsg().trim(),
        },
      });
      setStatus('отправлено Соне → она ответит в чате (Dialog pane), ~30с');
      setReplyMsg('');
    } catch (e) {
      setStatus('reply failed: ' + e.message);
    } finally {
      setBusy(false);
    }
  }

  function tryClose() {
    if (dirty() && !confirm('есть несохранённые изменения. закрыть всё равно?')) return;
    props.onClose?.();
  }

  onMount(() => {
    loadList();
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        if (active() && editable()) {
          e.preventDefault();
          save();
        }
        return;
      }
      if (e.key === 'Escape') {
        const tag = (e.target && e.target.tagName) || '';
        if (!/^(TEXTAREA|INPUT|SELECT)$/i.test(tag)) tryClose();
      }
    };
    window.addEventListener('keydown', onKey);
    onCleanup(() => window.removeEventListener('keydown', onKey));
  });

  /** Чёрно-белый рендер строки списка. По клику открывает файл (skills) или
   * ничего не делает (tools/packages — read-only). */
  function ListRow(p) {
    const it = p.item;
    const meta = p.meta;  // правый текст (размер / count)
    const isOn = () => editable() && active()?.path === it.path;
    return (
      <button
        classList={{
          'ws-item': true,
          on: isOn(),
          readonly: !editable(),
        }}
        onClick={() => editable() && openFile(it)}
        disabled={!editable()}
        title={`${it.path}${meta ? ' · ' + meta : ''}`}
      >
        <span class="ws-item-name">{it.path || it.name}</span>
        <span class="ws-item-size">{meta}</span>
      </button>
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
          <span class="exit" onClick={tryClose} title="закрыть (Esc)">⏏</span>
        </div>

        <div class="workshop-body">
          <aside class="ws-list">
            <div class="ws-list-head">
              <span>{kind()} ({listCount()})</span>
              <Show when={editable()}>
                <button class="mini-btn" onClick={newFile} title="новый файл">+ new</button>
              </Show>
            </div>
            <div class="ws-list-scroll">
              <Show when={items().length > 0} fallback={<div class="ws-empty">пусто</div>}>
                <Show
                  when={kind() === 'packages'}
                  fallback={
                    <For each={items()}>
                      {(it) => (
                        <ListRow item={it} meta={`${Math.round(it.size / 102.4) / 10}k`} />
                      )}
                    </For>
                  }
                >
                  {/* packages — плоский список верхнеуровневых пакетов, без раскрытий */}
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
            </div>
          </aside>

          <main class="ws-editor">
            <Show
              when={editable()}
              fallback={
                <div class="ws-placeholder ws-readonly-note">
                  <div class="ws-readonly-title">read-only</div>
                  <div class="ws-readonly-desc">
                    {kind() === 'tools'
                      ? 'тулы — список без редактирования. Изменения через git.'
                      : 'пакеты — список без редактирования. Изменения через git.'}
                  </div>
                </div>
              }
            >
              <Show
                when={active()}
                fallback={<div class="ws-placeholder">выбери файл слева</div>}
              >
                <div class="ws-editor-head">
                  <span class="ws-path">
                    {active().path}
                    <Show when={dirty()}><span class="ws-dirty" title="несохранённые изменения">●</span></Show>
                  </span>
                  <span class="ws-lang">{active().lang}</span>
                  <span class="spacer"></span>
                  <button class="mini-btn primary" disabled={busy() || !dirty()} onClick={save}
                    title="Ctrl+S">save</button>
                </div>
                <textarea
                  class="ws-textarea"
                  spellcheck={false}
                  value={content()}
                  onInput={(e) => setContent(e.currentTarget.value)}
                ></textarea>

                <div class="ws-reply">
                  <div class="ws-reply-label">спросить Соню про этот файл:</div>
                  <textarea
                    class="ws-reply-input"
                    placeholder="что это делает? почему так? упрости. напиши тест. …"
                    value={replyMsg()}
                    onInput={(e) => setReplyMsg(e.currentTarget.value)}
                  ></textarea>
                  <button class="mini-btn primary" disabled={busy() || !replyMsg().trim()} onClick={sendReply}>
                    ✉ send to Sonya
                  </button>
                </div>
              </Show>
            </Show>
          </main>
        </div>
      </div>
    </div>
  );
}
