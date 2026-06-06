/* ProjectWorkspace — dedicated project/workspace flow pane.
 *
 * Separate from Dialog. Shows active workspaces, project execution status,
 * subagent orchestration, and task progression. Replaces the Dialog pane
 * when workspace/project mode is active.
 *
 * См. docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md §3.
 */
import { For, Show } from 'solid-js';
import { settings, feed, activeWorkspaceId } from '../store.js';

export default function ProjectWorkspace(props) {
  const activeWorkspaces = () => {
    const ws = settings.workspaces.find((w) => w.id === activeWorkspaceId());
    return ws && ws.id !== 'main' ? [ws] : [];
  };

  // Collect subagent-related events from the feed
  const subagentEvents = () => feed.stream_events.filter(
    (e) => e.src === 'worker' || e.kind?.startsWith('task.') || e.kind?.includes('subagent')
  ).slice(-50).reverse();

  // Collect task progress events
  const taskProgress = () => feed.stream_events.filter(
    (e) => e.kind?.startsWith('task.') || e.kind?.includes('progress')
  );

  // Group tasks by task_id
  const taskGroups = () => {
    const groups = {};
    for (const ev of taskProgress()) {
      const tid = ev.task_id || ev.payload?.task_id || 'unknown';
      if (!groups[tid]) groups[tid] = [];
      groups[tid].push(ev);
    }
    return Object.entries(groups).slice(0, 10);
  };

  return (
    <div class="pane workspace-pane">
      <div class="workspace-pane-header">
        <h2>Workspace</h2>
        <span class="ws-status">
          <span class="conn-dot" classList={{ disconnected: !feed.connected }} />
          {activeWorkspaces().length} active
        </span>
      </div>

      <Show
        when={activeWorkspaces().length > 0}
        fallback={
          <div class="workspace-pane-empty">
            <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.2" opacity="0.3">
              <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
            <p>Нет активных рабочих пространств</p>
            <p class="muted">Выберите workspace в верхней панели</p>
          </div>
        }
      >
        {/* Active workspaces summary */}
        <div class="ws-active-list">
          <For each={activeWorkspaces()}>
            {(ws) => (
              <div class="ws-active-card">
                <div class="ws-active-top">
                  <span class="ws-active-name">{ws.name}</span>
                  <span classList={{ 'workspace-badge': true, [ws.type]: true }}>{ws.type}</span>
                </div>
                <div class="ws-active-path">{ws.path}</div>
              </div>
            )}
          </For>
        </div>

        {/* Inline project controls */}
        <div class="ws-project-controls">
          <button class="btn ghost" onClick={() => props.onNewProject?.()}>
            + Новый проект
          </button>
          <button class="btn ghost" onClick={() => props.onOpenWorkshop?.()}>
            Открыть Workshop
          </button>
        </div>

        {/* Task execution visibility */}
        <div class="ws-section">
          <h3 class="ws-section-title">Активные задачи</h3>
          <div class="ws-task-list">
            <Show
              when={taskGroups().length > 0}
              fallback={
                <div class="muted small" style="padding: 12px 0;">
                  Нет активных задач. Задачи появляются здесь при выполнении проектной работы.
                </div>
              }
            >
              <For each={taskGroups()}>
                {([taskId, events]) => {
                  const latest = events[events.length - 1];
                  const status = latest.payload?.status || 'in_progress';
                  const title = latest.payload?.title || latest.kind || taskId;
                  return (
                    <div class="ws-task-item">
                      <div class="ws-task-head">
                        <span classList={{ badge: true, [status]: true }}>{status}</span>
                        <span class="ws-task-id mono">{taskId.slice(0, 12)}</span>
                      </div>
                      <div class="ws-task-title">{title}</div>
                      <div class="ws-task-progress">
                        <div class="progress-bar">
                          <div class="progress-fill" style={`width: ${latest.payload?.progress || 0}%`} />
                        </div>
                        <span class="muted small">{latest.payload?.progress || 0}%</span>
                      </div>
                    </div>
                  );
                }}
              </For>
            </Show>
          </div>
        </div>

        {/* Subagent orchestration */}
        <div class="ws-section">
          <h3 class="ws-section-title">Субагенты</h3>
          <div class="ws-subagent-list">
            <Show
              when={subagentEvents().length > 0}
              fallback={
                <div class="muted small" style="padding: 12px 0;">
                  Нет активных субагентов. Субагенты создаются для параллельного выполнения подзадач.
                </div>
              }
            >
              <For each={subagentEvents().slice(0, 10)}>
                {(ev) => (
                  <div class="ws-subagent-row">
                    <span class="src-marker" data-src={ev.src} />
                    <div class="ws-subagent-body">
                      <span class="ws-subagent-kind">{ev.kind?.replace(/^outgoing\./, '').replace(/^internal\./, '')}</span>
                      <span class="ws-subagent-text">{ev.body || ev.text || ''}</span>
                    </div>
                    <span class="muted small">{ev.seq}</span>
                  </div>
                )}
              </For>
            </Show>
          </div>
        </div>
      </Show>
    </div>
  );
}
