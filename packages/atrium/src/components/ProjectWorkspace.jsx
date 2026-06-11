/* ProjectWorkspace is an observable project runtime for the one Sonya.
 * Internal workers are visible traces/subthreads, never separate chat actors.
 */
import { For, Show, createEffect, createSignal, onCleanup } from 'solid-js';
import {
  settings,
  feed,
  activeWorkspaceId,
  fetchProjectRuns,
  fetchProjectTraces,
  fetchWorkspacePolicy,
  checkProjectPolicy,
  setWorkspacePolicy,
  cancelProjectRun,
  controlProjectRun,
} from '../store.js';

const terminalStatuses = new Set(['done', 'failed', 'cancelled']);

export default function ProjectWorkspace(props) {
  const [runs, setRuns] = createSignal([]);
  const [traces, setTraces] = createSignal([]);
  const [workspacePolicy, setWorkspacePolicyState] = createSignal(null);
  const [policyVerdict, setPolicyVerdict] = createSignal(null);
  const [loading, setLoading] = createSignal(false);
  const [policyBusy, setPolicyBusy] = createSignal(false);

  const projectId = () => activeWorkspaceId();
  const activeProject = () => feed.projects.find((p) => p.project_id === projectId());
  const activeWorkspace = () => {
    const workspace = settings.workspaces.find((item) => item.id === projectId());
    if (workspace) return workspace;
    const project = activeProject();
    return project ? {
      id: project.project_id,
      name: project.title,
      path: project.workspace_path,
      type: 'project',
    } : null;
  };

  const refreshRuntime = async () => {
    const id = projectId();
    if (!id || id === 'main') return;
    setLoading(true);
    const [nextRuns, nextTraces, nextPolicy, nextVerdict] = await Promise.all([
      fetchProjectRuns(id),
      fetchProjectTraces(id),
      fetchWorkspacePolicy(id),
      checkProjectPolicy(id, 'shell_run'),
    ]);
    if (projectId() === id) {
      setRuns(nextRuns);
      setTraces(nextTraces);
      setWorkspacePolicyState(nextPolicy);
      setPolicyVerdict(nextVerdict);
      setLoading(false);
    }
  };

  createEffect(() => {
    projectId();
    refreshRuntime();
    const timer = setInterval(refreshRuntime, 5000);
    onCleanup(() => clearInterval(timer));
  });

  const executorRuns = () => runs().filter((run) => run.kind === 'project_executor');
  const activeRuns = () => executorRuns().filter((run) => !['completed', 'failed', 'cancelled'].includes(run.status));
  const visibleRuns = () => (activeRuns().length ? activeRuns() : executorRuns()).slice(0, 8);
  const workerSteps = () => visibleRuns().flatMap((run) =>
    (run.steps || []).map((step) => ({ ...step, run_id: run.run_id }))
  );

  const stepStatus = (step) => step.status || 'pending';
  const retryLabel = (step) => Number(step.retry_count || 0) > 0
    ? `повтор ${step.retry_count}/${step.max_retries || step.retry_count}`
    : '';
  const traceTitle = (trace) => trace.step_type === 'checkpoint'
    ? 'checkpoint'
    : trace.step_type === 'outcome' ? 'результат' : trace.step_type;
  const cancelRun = async (runId) => {
    if (await cancelProjectRun(projectId(), runId)) await refreshRuntime();
  };
  const controlRun = async (runId, action) => {
    if (await controlProjectRun(projectId(), runId, action)) await refreshRuntime();
  };
  const toggleFullAccess = async () => {
    const id = projectId();
    if (!id || id === 'main' || policyBusy()) return;
    setPolicyBusy(true);
    const updated = await setWorkspacePolicy(id, {
      full_system_access: !workspacePolicy()?.full_system_access,
    });
    if (updated && projectId() === id) {
      setWorkspacePolicyState(updated);
      setPolicyVerdict(await checkProjectPolicy(id, 'shell_run'));
    }
    setPolicyBusy(false);
  };
  const fullAccessEnabled = () => Boolean(workspacePolicy()?.full_system_access);
  const policySource = () => policyVerdict()?.source || (workspacePolicy() ? 'workspace_policy' : 'loading');
  const shellVerdict = () => policyVerdict()?.verdict || 'unknown';

  return (
    <div class="pane workspace-pane">
      <div class="workspace-pane-header">
        <h2>Проект</h2>
        <span class="ws-status">
          <span class="conn-dot" classList={{ disconnected: !feed.connected }} />
          {loading() ? 'обновление' : 'runtime'}
        </span>
      </div>

      <Show when={activeWorkspace()} fallback={<div class="workspace-pane-empty">Проект не найден</div>}>
        {(workspace) => (
          <>
            <div class="ws-active-list">
              <div class="ws-active-card">
                <div class="ws-active-top">
                  <span class="ws-active-name">{workspace().name}</span>
                  <span class="workspace-badge project">{activeProject()?.status || 'project'}</span>
                </div>
                <div class="ws-active-path">{workspace().path || 'Папка проекта не задана'}</div>
              </div>
            </div>

            <div class="ws-project-controls">
              <button class="btn ghost" onClick={() => props.onOpenWorkshop?.()}>Открыть Workshop</button>
              <button class="btn ghost" onClick={refreshRuntime}>Обновить runtime</button>
            </div>

            <div classList={{ 'ws-policy-card': true, enabled: fullAccessEnabled() }}>
              <div class="ws-policy-main">
                <div>
                  <div class="ws-policy-title">Full-system access</div>
                  <div class="ws-policy-copy">
                    {fullAccessEnabled()
                      ? 'Main Sonya can work under the wider workspace policy. Internal subagents remain project-scoped.'
                      : 'Project actions use conservative consent policy. Enable only when Ivan wants main Sonya to work wider than the project folder.'}
                  </div>
                </div>
                <button
                  class="btn ghost ws-policy-toggle"
                  disabled={policyBusy()}
                  onClick={toggleFullAccess}
                >
                  {policyBusy() ? 'Saving...' : fullAccessEnabled() ? 'Disable' : 'Enable'}
                </button>
              </div>
              <div class="ws-policy-meta">
                <span classList={{ 'ws-policy-pill': true, enabled: fullAccessEnabled() }}>
                  {fullAccessEnabled() ? 'enabled' : 'restricted'}
                </span>
                <span>shell_run: {shellVerdict()}</span>
                <span>source: {policySource()}</span>
              </div>
            </div>

            <div class="ws-section">
              <h3 class="ws-section-title">Ход выполнения</h3>
              <div class="ws-task-list">
                <Show when={visibleRuns().length > 0} fallback={
                  <div class="muted small ws-empty">Запусков проекта пока нет.</div>
                }>
                  <For each={visibleRuns()}>
                    {(run) => (
                      <div class="ws-task-item">
                        <div class="ws-task-head">
                          <span classList={{ badge: true, [run.status]: true }}>{run.status}</span>
                          <span class="ws-task-id mono">{run.run_id}</span>
                        </div>
                        <div class="ws-task-title">{run.summary || 'Sonya выполняет проектную задачу'}</div>
                        <div class="ws-task-progress">
                          <div class="progress-bar">
                            <div class="progress-fill" style={`width: ${run.progress?.percent || 0}%`} />
                          </div>
                          <span class="muted small">{run.progress?.percent || 0}%</span>
                        </div>
                        <div class="ws-run-counts">
                          <span>{run.progress?.completed || 0} готово</span>
                          <span>{run.progress?.running || 0} в работе</span>
                          <Show when={run.progress?.failed}><span class="ws-error">{run.progress.failed} ошибок</span></Show>
                          <Show when={run.progress?.cancelled}><span>{run.progress.cancelled} отменено</span></Show>
                          <Show when={['pending', 'running'].includes(run.status)}>
                            <button class="btn ghost" onClick={() => controlRun(run.run_id, 'pause')}>Pause</button>
                            <button class="btn ghost ws-cancel-run" onClick={() => cancelRun(run.run_id)}>Отменить</button>
                          </Show>
                          <Show when={run.status === 'paused'}>
                            <button class="btn ghost" onClick={() => controlRun(run.run_id, 'resume')}>Resume</button>
                            <button class="btn ghost ws-cancel-run" onClick={() => cancelRun(run.run_id)}>Cancel</button>
                          </Show>
                          <Show when={run.status === 'waiting_approval'}>
                            <button class="btn ghost" onClick={() => controlRun(run.run_id, 'approve')}>Approve</button>
                            <button class="btn ghost ws-cancel-run" onClick={() => controlRun(run.run_id, 'deny')}>Deny</button>
                          </Show>
                        </div>
                        <Show when={run.result || run.error}>
                          <div classList={{ 'ws-run-result': true, error: Boolean(run.error) }}>
                            {run.error || run.result}
                          </div>
                        </Show>
                      </div>
                    )}
                  </For>
                </Show>
              </div>
            </div>

            <div class="ws-section">
              <h3 class="ws-section-title">Внутренние исполнители</h3>
              <div class="ws-subagent-list">
                <Show when={workerSteps().length > 0} fallback={
                  <div class="muted small ws-empty">Sonya пока не создавала внутренних исполнителей.</div>
                }>
                  <For each={workerSteps()}>
                    {(step) => (
                      <div class="ws-subagent-row">
                        <span classList={{ 'ws-worker-dot': true, [stepStatus(step)]: true }} />
                        <div class="ws-subagent-body">
                          <div class="ws-worker-meta">
                            <span class="ws-subagent-kind">{stepStatus(step)}</span>
                            <Show when={retryLabel(step)}><span class="ws-retry">{retryLabel(step)}</span></Show>
                            <span class="mono muted small">{step.provider}/{step.model}</span>
                          </div>
                          <span class="ws-subagent-text">{step.task}</span>
                          <Show when={terminalStatuses.has(stepStatus(step)) && step.result}>
                            <span class="ws-worker-result">{step.result}</span>
                          </Show>
                        </div>
                        <span class="muted small mono">{step.subagent_id?.slice(0, 12)}</span>
                      </div>
                    )}
                  </For>
                </Show>
              </div>
            </div>

            <div class="ws-section">
              <h3 class="ws-section-title">Трасса выполнения</h3>
              <div class="ws-trace-list">
                <Show when={traces().length > 0} fallback={
                  <div class="muted small ws-empty">Checkpoint и результаты появятся здесь.</div>
                }>
                  <For each={traces().slice(0, 30)}>
                    {(trace) => (
                      <div class="ws-trace-row">
                        <span classList={{ 'ws-trace-type': true, [trace.step_type]: true }}>{traceTitle(trace)}</span>
                        <div class="ws-trace-content">
                          <span>{trace.content || trace.outcome}</span>
                          <span class="mono muted small">
                            {[trace.provider, trace.model, trace.tool_name].filter(Boolean).join(' · ')}
                          </span>
                        </div>
                        <span class="muted small mono">#{trace.step_seq}</span>
                      </div>
                    )}
                  </For>
                </Show>
              </div>
            </div>
          </>
        )}
      </Show>
    </div>
  );
}
