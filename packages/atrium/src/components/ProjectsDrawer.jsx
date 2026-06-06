import { createSignal, For, Show } from 'solid-js';
import { settings, activeWorkspaceId, switchWorkspace, createWorkspace, removeWorkspace, pickProjectFolder } from '../store.js';

function relTime(ts) {
  if (!ts) return '';
  const diff = Date.now() - ts;
  if (diff < 60000) return 'только что';
  if (diff < 3600000) return Math.floor(diff / 60000) + 'м назад';
  if (diff < 86400000) return Math.floor(diff / 3600000) + 'ч назад';
  if (diff < 604800000) return Math.floor(diff / 86400000) + 'д назад';
  return new Date(ts).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

const TYPE_ICONS = {
  local: '📁',
  remote: '☁️',
};

export default function ProjectsDrawer(props) {
  const [showForm, setShowForm] = createSignal(false);
  const [formName, setFormName] = createSignal('');
  const [formDesc, setFormDesc] = createSignal('');
  const [formType, setFormType] = createSignal('local');
  const [formPath, setFormPath] = createSignal('');
  const [formPathHandle, setFormPathHandle] = createSignal(null);

  async function handleBrowseFolder() {
    const result = await pickProjectFolder();
    if (result) {
      setFormPath(result.path);
      setFormPathHandle(result.handle);
    }
  }

  function handleCreate(e) {
    e.preventDefault();
    if (!formName().trim() || !formPath().trim()) return;
    createWorkspace({
      id: 'ws_' + Date.now(),
      name: formName().trim(),
      description: formDesc().trim(),
      path: formPath().trim(),
      type: formType(),
      status: 'idle',
    });
    setFormName('');
    setFormDesc('');
    setFormPath('');
    setFormPathHandle(null);
    setShowForm(false);
  }

  function handleRemove(id, name) {
    switchWorkspace('main');
    removeWorkspace(id);
  }

  return (
    <>
      {/* Overlay */}
      <Show when={props.open()}>
        <div class="drawer-overlay" onClick={props.onClose} />
      </Show>

      {/* Drawer */}
      <div classList={{ 'projects-drawer': true, open: props.open() }}>
        <div class="drawer-header">
          <h3>ПРОЕКТЫ</h3>
          <div class="drawer-header-actions">
            <button class="drawer-add-btn" onClick={() => setShowForm(!showForm())} title="Новый проект">+</button>
            <button class="drawer-close-btn" onClick={props.onClose} title="Закрыть">◀</button>
          </div>
        </div>

        <Show when={showForm()}>
          <form class="project-create-form" onSubmit={handleCreate}>
            <input
              type="text"
              placeholder="Название проекта"
              value={formName()}
              onInput={(e) => setFormName(e.currentTarget.value)}
              required
            />
            <input
              type="text"
              placeholder="Описание (что это за проект)"
              value={formDesc()}
              onInput={(e) => setFormDesc(e.currentTarget.value)}
            />
            <div class="path-picker-row">
              <input
                type="text"
                placeholder="Путь к папке проекта"
                value={formPath()}
                onInput={(e) => setFormPath(e.currentTarget.value)}
                required
              />
              <button type="button" class="browse-btn" onClick={handleBrowseFolder} title="Выбрать папку">📂</button>
            </div>
            <div class="form-type-row">
              <label classList={{ 'type-opt': true, active: formType() === 'local' }}>
                <input type="radio" name="ws-type" value="local" checked={formType() === 'local'} onChange={() => setFormType('local')} />
                📁 Локальный
              </label>
              <label classList={{ 'type-opt': true, active: formType() === 'remote' }}>
                <input type="radio" name="ws-type" value="remote" checked={formType() === 'remote'} onChange={() => setFormType('remote')} />
                ☁️ Удалённый
              </label>
            </div>
            <div class="form-actions">
              <button type="button" onClick={() => { setShowForm(false); setFormName(''); setFormDesc(''); setFormPath(''); }}>отмена</button>
              <button type="submit" class="primary">создать проект</button>
            </div>
          </form>
        </Show>

        <div class="drawer-list">
          <For each={settings.workspaces.filter(w => w.id !== 'main')}>
            {(ws) => (
              <div
                classList={{ 'project-card': true, active: activeWorkspaceId() === ws.id }}
                onClick={() => { switchWorkspace(ws.id); props.onClose(); }}
              >
                <div class="project-card-top">
                  <span class="project-status-dot" classList={{ idle: ws.status === 'idle' || !ws.status, active: ws.status === 'active', error: ws.status === 'error' }} />
                  <span class="project-type-icon">{TYPE_ICONS[ws.type] || '📁'}</span>
                  <span class="project-name">{ws.name}</span>
                  <span class="project-time">{relTime(ws.last_message_at || ws.created_at)}</span>
                    <button
                      class="project-del-btn"
                      onClick={(e) => { e.stopPropagation(); handleRemove(ws.id, ws.name); }}
                      title="Удалить проект">✕</button>
                </div>
                <Show when={ws.path}>
                  <div class="project-path">{ws.path}</div>
                </Show>
                <Show when={ws.description}>
                  <div class="project-desc">{ws.description}</div>
                </Show>
              </div>
            )}
          </For>
        </div>

        <Show when={settings.workspaces.filter(w => w.id !== 'main').length === 0}>
          <div class="drawer-empty">
            <span class="drawer-empty-icon">📂</span>
            <p>Нет проектов. Создайте первый, чтобы работать над кодом вместе с Соней.</p>
          </div>
        </Show>
      </div>
    </>
  );
}
