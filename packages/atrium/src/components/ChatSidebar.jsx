import { createSignal, For, Show } from 'solid-js';
import { settings, feed, activeWorkspaceId, switchWorkspace, createWorkspace, removeWorkspace, fetchProjects, createProject, deleteProject } from '../store.js';

const STATUS_LABELS = {
  in_progress: 'в работе',
  waiting_choice: 'жду выбор',
  waiting: 'ожидает',
  completed: 'завершён',
  cancelled: 'отменён',
  active: 'активен',
  paused: 'на паузе',
  closed: 'закрыт',
  archived: 'в архиве'
};

function relTime(ts) {
  if (!ts) return '';
  const diff = Date.now() - ts;
  if (diff < 60000) return 'только что';
  if (diff < 3600000) return Math.floor(diff / 60000) + 'м';
  if (diff < 86400000) return Math.floor(diff / 3600000) + 'ч';
  return Math.floor(diff / 86400000) + 'д';
}

export default function ChatSidebar() {
  const [showForm, setShowForm] = createSignal(false);
  const [newName, setNewName] = createSignal('');
  const [newDesc, setNewDesc] = createSignal('');
  const [showProjectForm, setShowProjectForm] = createSignal(false);
  const [projName, setProjName] = createSignal('');
  const [projDesc, setProjDesc] = createSignal('');

  function handleCreate(e) {
    e.preventDefault();
    if (!newName().trim()) return;
    createWorkspace({
      id: 'ws_' + Date.now(),
      name: newName().trim(),
      description: newDesc().trim(),
      path: '',
    });
    setNewName('');
    setNewDesc('');
    setShowForm(false);
  }

  async function handleCreateProject(e) {
    e.preventDefault();
    if (!projName().trim()) return;
    await createProject(projName().trim(), projDesc().trim(), '');
    setProjName('');
    setProjDesc('');
    setShowProjectForm(false);
  }

  return (
    <div class="chat-sidebar">
      <div class="chat-sidebar-header">
        <h3>Чаты</h3>
        <button class="chat-add-btn" onClick={() => setShowForm(!showForm())} title="Новый чат">+</button>
      </div>

      <Show when={showForm()}>
        <form class="chat-add-form" onSubmit={handleCreate}>
          <input
            type="text"
            placeholder="Название чата"
            value={newName()}
            onInput={(e) => setNewName(e.currentTarget.value)}
            required
          />
          <input
            type="text"
            placeholder="Описание (необязательно)"
            value={newDesc()}
            onInput={(e) => setNewDesc(e.currentTarget.value)}
          />
          <div class="chat-add-actions">
            <button type="button" onClick={() => { setShowForm(false); setNewName(''); setNewDesc(''); }}>отмена</button>
            <button type="submit" class="primary">создать</button>
          </div>
        </form>
      </Show>

      <div class="chat-sidebar-list">
        <For each={settings.workspaces}>
          {(ws) => (
            <div
              classList={{ 'chat-item': true, active: activeWorkspaceId() === ws.id }}
              onClick={() => switchWorkspace(ws.id)}
            >
              <div class="chat-item-top">
                <span class="chat-item-name">{ws.name}</span>
                <span class="chat-item-time">{relTime(ws.last_message_at || ws.created_at)}</span>
              </div>
              <Show when={ws.description}>
                <div class="chat-item-desc">{ws.description}</div>
              </Show>
              <Show when={ws.id !== 'main'}>
                <button
                  class="chat-item-del"
                  onClick={(e) => { e.stopPropagation(); if (confirm('Удалить чат "' + ws.name + '"?')) removeWorkspace(ws.id); }}
                  title="Удалить чат">✕</button>
              </Show>
            </div>
          )}
        </For>
      </div>

      <Show when={feed.projects.length > 0}>
        <div class="chat-sidebar-header">
          <h3>Проекты</h3>
          <button class="chat-add-btn" onClick={() => setShowProjectForm(!showProjectForm())} title="Новый проект">+</button>
        </div>
        <Show when={showProjectForm()}>
          <form class="chat-add-form" onSubmit={handleCreateProject}>
            <input
              type="text"
              placeholder="Название проекта"
              value={projName()}
              onInput={(e) => setProjName(e.currentTarget.value)}
              required
            />
            <input
              type="text"
              placeholder="Описание"
              value={projDesc()}
              onInput={(e) => setProjDesc(e.currentTarget.value)}
            />
            <div class="chat-add-actions">
              <button type="button" onClick={() => { setShowProjectForm(false); setProjName(''); setProjDesc(''); }}>отмена</button>
              <button type="submit" class="primary">создать</button>
            </div>
          </form>
        </Show>
        <div class="chat-sidebar-list">
          <For each={feed.projects}>
            {(proj) => (
              <div
                classList={{ 'chat-item': true, active: activeWorkspaceId() === proj.project_id }}
                onClick={() => switchWorkspace(proj.project_id)}
              >
                <div class="chat-item-top">
                  <span class="chat-item-name">{proj.title}</span>
                  <span class="chat-item-time">{relTime(proj.last_activity_at ? new Date(proj.last_activity_at).getTime() : undefined)}</span>
                </div>
                <Show when={proj.description}>
                  <div class="chat-item-desc">{proj.description}</div>
                </Show>
                <div class="chat-item-desc" style="font-size: 0.8em; color: var(--color-subtext); margin-top: 4px;">
                  {STATUS_LABELS[proj.status] || proj.status}
                </div>
                <button
                  class="chat-item-del"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm('Удалить проект "' + proj.title + '"? Это также удалит все логи выполнения.')) {
                      deleteProject(proj.project_id);
                      if (activeWorkspaceId() === proj.project_id) switchWorkspace('main');
                    }
                  }}
                  title="Удалить проект">✕</button>
              </div>
            )}
          </For>
        </div>
      </Show>
    </div>
  );
}
