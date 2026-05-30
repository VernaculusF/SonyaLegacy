/* Workshop — обозрение и редактор Сониного «кода жизни»:
 *   - skills    : Python в src/sonya/skills/builtins/*.py
 *   - tools     : hot-loadable плагины в src/sonya/tools/plugins/*.py
 *   - packages  : packages/* (atrium, tg-userbot) — структурный обзор
 *
 * Можно: смотреть список / читать / писать (skills+tools) / тестово
 * запускать (tools) / задавать вопрос Соне про этот файл (reply).
 *
 * Открывается из header («⚙ workshop») как полноэкранный overlay.
 */
import { createSignal, onMount, onCleanup, For, Show } from 'solid-js';
import { settings } from '../store.js';

/**
 * TreeNode — рекурсивный узел дерева для kind='packages'.
 *
 * node.type === 'dir':  раскрывающаяся папка (свой createSignal collapsed).
 * node.type === 'file': кликабельный файл (открывает в редакторе).
 *
 * skills/tools остаются плоским списком и рендерятся отдельно.
 */
function TreeNode(props) {
  const { node, depth = 0, isActive, onPick } = props;
  const [open, setOpen] = createSignal(depth === 0);  // top-level packages раскрыты по умолчанию

  if (node.type === 'file') {
    return (
      <button
        classList={{ 'ws-item': true, 'ws-tree-file': true, on: isActive(node) }}
        style={{ 'padding-left': `${10 + depth * 12}px` }}
        onClick={() => onPick(node)}
        title={`${node.path} · ${node.size}b`}
      >
        <span class="ws-item-name">{node.name}</span>
        <span class="ws-item-size">{Math.round(node.size / 102.4) / 10}k</span>
      </button>
    );
  }
  // dir
  return (
    <div class="ws-tree-dir">
      <button
        class="ws-tree-dir-head"
        style={{ 'padding-left': `${10 + depth * 12}px` }}
        onClick={() => setOpen(!open())}
        title={node.path}
      >
        <span class="ws-tree-chev">{open() ? '▾' : '▸'}</span>
        <span class="ws-tree-dir-name">{node.name}</span>
        <span class="ws-tree-dir-count">{(node.children || []).length}</span>
      </button>
      <Show when={open()}>
        <div class="ws-tree-children">
          <For each={node.children || []}>
            {(child) => <TreeNode node={child} depth={depth + 1} isActive={isActive} onPick={onPick} />}
          </For>
        </div>
      </Show>
    </div>
  );
}

const KINDS = [
  { id: 'skills', label: 'skills', desc: 'Python поведение (skills.run)' },
  { id: 'tools', label: 'tools', desc: 'hot-loadable плагины тулов' },
  { id: 'packages', label: 'packages', desc: 'подпроекты (atrium, tg-userbot)' },
];

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
  const [test, setTest] = createSignal({ input: '', output: '' });
  const [replyMsg, setReplyMsg] = createSignal('');
  const dirty = () => content() !== savedContent();

  // Recursive file count for tree (packages); flat length otherwise.
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
    } finally {
      setBusy(false);
    }
  }

  async function openFile(it) {
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
    if (!active()) return;
    if (kind() === 'packages') {
      setStatus('packages — read-only из workshop (правь через git как обычный код)');
      return;
    }
    setBusy(true);
    setStatus('');
    try {
      await api('/api/atrium/workshop/write', {
        method: 'POST',
        body: { kind: kind(), path: active().path, content: content() },
      });
      setSavedContent(content());
      setStatus(`saved → ${active().path}`);
      // Refresh list (size may have changed; new files appear).
      loadList();
    } catch (e) {
      setStatus('save failed: ' + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function newFile() {
    if (kind() === 'packages') return;
    if (dirty() && !confirm('есть несохранённые изменения. сбросить?')) return;
    const name = prompt('имя файла (например: my_helper.py):');
    if (!name || !/^[a-z0-9_]+\.py$/i.test(name)) {
      setStatus('only .py with [a-z0-9_]');
      return;
    }
    const stub = kind() === 'tools'
      ? `"""${name} — hot-loadable tool plugin."""\n\ndef run(arg: str) -> str:\n    return f"echo: {arg}"\n`
      : `"""${name} — skill module."""\n\ndef run(ctx) -> str:\n    return "TODO"\n`;
    setActive({ path: name, name, lang: 'python', size: stub.length });
    setContent(stub);
    setSavedContent('');  // new file — anything counts as dirty until saved
    setStatus('new (unsaved) — Ctrl+S чтобы сохранить');
  }

  async function runTest() {
    if (!active()) return;
    setBusy(true);
    setStatus('');
    try {
      const r = await api('/api/atrium/workshop/test', {
        method: 'POST',
        body: { kind: kind(), path: active().path, input: test().input },
      });
      setTest({ ...test(), output: r.result || JSON.stringify(r) });
    } catch (e) {
      setTest({ ...test(), output: 'error: ' + e.message });
    } finally {
      setBusy(false);
    }
  }

  async function sendReply() {
    if (!replyMsg().trim()) return;
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
      // Ctrl/Cmd+S → save (only when an active file + editable kind)
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        if (active() && kind() !== 'packages') {
          e.preventDefault();
          save();
        }
        return;
      }
      // Esc — only close when focus is NOT in a text field, otherwise let it
      // act normally (so Esc inside the textarea doesn't kill the editor).
      if (e.key === 'Escape') {
        const tag = (e.target && e.target.tagName) || '';
        if (!/^(TEXTAREA|INPUT|SELECT)$/i.test(tag)) tryClose();
      }
    };
    window.addEventListener('keydown', onKey);
    onCleanup(() => window.removeEventListener('keydown', onKey));
  });

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
                  onClick={() => { setKind(k.id); setActive(null); setContent(''); loadList(); }}
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
              <Show when={kind() !== 'packages'}>
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
                        <button
                          classList={{ 'ws-item': true, on: active()?.path === it.path }}
                          onClick={() => openFile(it)}
                          title={`${it.path} · ${it.size}b`}
                        >
                          <span class="ws-item-name">{it.path}</span>
                          <span class="ws-item-size">{Math.round(it.size / 102.4) / 10}k</span>
                        </button>
                      )}
                    </For>
                  }
                >
                  <For each={items()}>
                    {(node) => (
                      <TreeNode
                        node={node}
                        depth={0}
                        isActive={(n) => active()?.path === n.path}
                        onPick={(n) => openFile(n)}
                      />
                    )}
                  </For>
                </Show>
              </Show>
            </div>
          </aside>

          <main class="ws-editor">
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
                <Show when={kind() !== 'packages'}>
                  <button class="mini-btn primary" disabled={busy() || !dirty()} onClick={save}
                    title="Ctrl+S">save</button>
                </Show>
              </div>
              <textarea
                class="ws-textarea"
                spellcheck={false}
                value={content()}
                onInput={(e) => setContent(e.currentTarget.value)}
              ></textarea>

              <Show when={kind() === 'tools'}>
                <div class="ws-test">
                  <div class="ws-test-row">
                    <input
                      type="text"
                      placeholder="input для run(arg) …"
                      value={test().input}
                      onInput={(e) => setTest({ ...test(), input: e.currentTarget.value })}
                    />
                    <button class="mini-btn" disabled={busy()} onClick={runTest}>▶ run</button>
                  </div>
                  <Show when={test().output}>
                    <pre class="ws-test-out">{test().output}</pre>
                  </Show>
                </div>
              </Show>
            </Show>

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
          </main>
        </div>
      </div>
    </div>
  );
}
