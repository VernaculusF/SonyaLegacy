import { createSignal, For, Show } from 'solid-js';
import { feed, activeWorkspaceId, switchWorkspace, createProject, deleteProject } from '../store.js';

const STATUS_LABELS = {
  in_progress: 'in progress',
  waiting_choice: 'waiting for choice',
  waiting: 'waiting',
  completed: 'completed',
  cancelled: 'cancelled',
};

function relTime(ts) {
  if (!ts) return '';
  const diff = Date.now() - ts;
  if (diff < 60000) return 'now';
  if (diff < 3600000) return Math.floor(diff / 60000) + 'm';
  if (diff < 86400000) return Math.floor(diff / 3600000) + 'h';
  return Math.floor(diff / 86400000) + 'd';
}

export default function ChatSidebar(props) {
  const [showProjectForm, setShowProjectForm] = createSignal(false);
  const [projName, setProjName] = createSignal('');
  const [projDesc, setProjDesc] = createSignal('');
  const [projPath, setProjPath] = createSignal('');
  const [createError, setCreateError] = createSignal('');

  function resetForm() {
    setProjName('');
    setProjDesc('');
    setProjPath('');
    setCreateError('');
    setShowProjectForm(false);
  }

  function closeDrawer() {
    props.onClose?.();
  }

  function selectChat(id) {
    switchWorkspace(id);
    closeDrawer();
  }

  async function handleCreateProject(e) {
    e.preventDefault();
    if (!projName().trim() || !projPath().trim()) return;
    setCreateError('');
    const created = await createProject(
      projName().trim(),
      projDesc().trim(),
      projPath().trim(),
    );
    if (!created?.project_id) {
      setCreateError('Project creation failed. Check the workspace path and connection.');
      return;
    }
    resetForm();
    selectChat(created.project_id);
  }

  return (
    <>
      <Show when={props.open()}>
        <div class="chat-drawer-overlay" onClick={closeDrawer} />
      </Show>
      <div classList={{ 'chat-sidebar': true, open: props.open() }}>
        <div class="chat-sidebar-header">
          <h3>Chats</h3>
          <button class="chat-close-btn" onClick={closeDrawer} title="Close chat list">
            x
          </button>
        </div>
        <div class="chat-sidebar-list">
          <div
            classList={{ 'chat-item': true, active: activeWorkspaceId() === 'main' }}
            onClick={() => selectChat('main')}
          >
            <div class="chat-item-top">
              <span class="chat-item-name">main</span>
            </div>
            <div class="chat-item-desc">Sonya's home</div>
          </div>
        </div>

        <div class="chat-sidebar-header">
          <h3>Projects</h3>
          <button
            class="chat-add-btn"
            onClick={() => setShowProjectForm(!showProjectForm())}
            title="New project"
          >
            +
          </button>
        </div>

        <Show when={showProjectForm()}>
          <form class="chat-add-form" onSubmit={handleCreateProject}>
            <input
              type="text"
              placeholder="Project name"
              value={projName()}
              onInput={(e) => setProjName(e.currentTarget.value)}
              required
            />
            <input
              type="text"
              placeholder="Description"
              value={projDesc()}
              onInput={(e) => setProjDesc(e.currentTarget.value)}
            />
            <input
              type="text"
              placeholder="/local/path, C:\\path, or ssh://user@host/absolute/path"
              value={projPath()}
              onInput={(e) => setProjPath(e.currentTarget.value)}
              required
            />
            <div class="chat-add-hint">
              With full computer access enabled, Sonya can create a project chat from any reachable folder.
            </div>
            <Show when={createError()}>
              <div class="ws-error">{createError()}</div>
            </Show>
            <div class="chat-add-actions">
              <button type="button" onClick={resetForm}>cancel</button>
              <button type="submit" class="primary">create project</button>
            </div>
          </form>
        </Show>

        <div class="chat-sidebar-list">
          <For each={feed.projects}>
            {(project) => (
              <div
                classList={{ 'chat-item': true, active: activeWorkspaceId() === project.project_id }}
                onClick={() => selectChat(project.project_id)}
              >
                <div class="chat-item-top">
                  <span class="chat-item-name">{project.title}</span>
                  <span class="chat-item-time">
                    {relTime(project.last_activity_at ? new Date(project.last_activity_at).getTime() : undefined)}
                  </span>
                </div>
                <Show when={project.description}>
                  <div class="chat-item-desc">{project.description}</div>
                </Show>
                <Show when={project.workspace_path}>
                  <div class="chat-item-desc mono">{project.workspace_path}</div>
                </Show>
                <div class="chat-item-desc">{STATUS_LABELS[project.status] || project.status}</div>
                <button
                  class="chat-item-del"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Delete project "${project.title}" and its execution logs?`)) {
                      deleteProject(project.project_id);
                      if (activeWorkspaceId() === project.project_id) selectChat('main');
                    }
                  }}
                  title="Delete project"
                >
                  x
                </button>
              </div>
            )}
          </For>
        </div>
      </div>
    </>
  );
}
