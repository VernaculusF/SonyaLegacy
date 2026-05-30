/* consoleApi.js — thin client for the admin/operator endpoints, called from
 * the Atrium Console with the X-Atrium-Token header (no cookie). The backend
 * auth_middleware now accepts the token on any /api/* path.
 */
import { settings } from './store.js';

async function call(path, { method = 'GET', body, raw = false } = {}) {
  const url = `http://${settings.vps_host}${path}`;
  const headers = { 'X-Atrium-Token': settings.atrium_token || '' };
  const opts = { method, headers };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(url, opts);
  if (raw) return r;
  const text = await r.text();
  let json;
  try { json = JSON.parse(text); } catch { json = { error: text }; }
  if (!r.ok) throw new Error(json.error || `HTTP ${r.status}`);
  return json;
}

// --- operator ---
export const getSnapshot = () => call('/api/operator/snapshot');
export const getLiveSteps = (since = 0, limit = 60) =>
  call(`/api/operator/live?since=${since}&limit=${limit}`);
export const triggerActive = (reason = 'console') =>
  call('/api/operator/trigger-active', { method: 'POST', body: { reason } });
export const injectMessage = (text, channel = 'telegram') =>
  call('/api/operator/inject-message', { method: 'POST', body: { text, channel } });
export const taskAction = (taskId, action, reason = '') =>
  call(`/api/operator/task/${encodeURIComponent(taskId)}/action`, { method: 'POST', body: { action, reason } });

// --- tasks ---
export const getTasks = () => call('/api/tasks');
export const getTaskDetail = (id) => call(`/api/tasks/${encodeURIComponent(id)}`);
export const deleteTask = (id) => call(`/api/tasks/${encodeURIComponent(id)}`, { method: 'DELETE' });

// --- selfmod ---
export const getSelfmodList = (status) =>
  call(`/api/selfmod/list${status ? `?status=${status}` : ''}`);
export const getSelfmod = (id) => call(`/api/selfmod/${encodeURIComponent(id)}`);
export const approveSelfmod = (id) => call(`/api/selfmod/${encodeURIComponent(id)}/approve`, { method: 'POST' });
export const denySelfmod = (id) => call(`/api/selfmod/${encodeURIComponent(id)}/deny`, { method: 'POST' });

// --- approvals ---
export const getApprovals = () => call('/api/approvals');
export const decideApproval = (id, decision) =>
  call(`/api/approvals/${encodeURIComponent(id)}/${decision}`, { method: 'POST' });

// --- providers ---
export const getProviders = () => call('/api/providers');
export const setProviderSettings = (body) => call('/api/providers/settings', { method: 'POST', body });
export const addProviderKey = (body) => call('/api/providers/keys', { method: 'POST', body });
export const updateProviderKey = (id, body) => call(`/api/providers/keys/${encodeURIComponent(id)}`, { method: 'POST', body });
export const deleteProviderKey = (id) => call(`/api/providers/keys/${encodeURIComponent(id)}/delete`, { method: 'POST' });
export const testProviderKey = (id) => call(`/api/providers/keys/${encodeURIComponent(id)}/test`, { method: 'POST' });
export const setProviderKeyStatus = (id, status) => call(`/api/providers/keys/${encodeURIComponent(id)}/status`, { method: 'POST', body: { status } });
export const refreshBalance = (id) =>
  call(id ? `/api/providers/keys/${encodeURIComponent(id)}/balance/refresh` : '/api/providers/balance/refresh', { method: 'POST' });

// --- core ---
export const getCoreStatus = () => call('/api/core/status');
export const startCore = (mode = 'full') => call(`/api/core/start?mode=${mode}`, { method: 'POST' });
export const stopCore = () => call('/api/core/stop', { method: 'POST' });
export const getCoreLogs = (lines = 80) => call(`/api/core/logs?lines=${lines}`);

// --- substrate ---
export const getSubstrate = () => call('/api/substrate');
export const getLlmCalls = (limit = 60) => call(`/api/llm_calls?limit=${limit}`);

// --- repo ---
export const getRepoStatus = () => call('/api/atrium/repo/status');
export const repoCommit = (message) => call('/api/atrium/repo/commit', { method: 'POST', body: { message } });
export const repoPush = () => call('/api/atrium/repo/push', { method: 'POST' });
export const repoRevert = (mode, ref) => call('/api/atrium/repo/revert', { method: 'POST', body: { mode, ref } });
