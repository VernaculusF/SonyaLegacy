/* First-run onboarding: asks for VPS host + admin token. */
import { createSignal } from 'solid-js';
import { settings, updateSetting } from '../store.js';

export default function Onboarding(props) {
  const [host, setHost] = createSignal(settings.vps_host || '');
  const [token, setToken] = createSignal('');
  const [error, setError] = createSignal('');
  const [testing, setTesting] = createSignal(false);

  async function tryConnect() {
    if (!host().trim() || !token().trim()) {
      setError('заполни оба поля');
      return;
    }
    setError('');
    setTesting(true);
    try {
      // Quick smoke-check via nudge endpoint with empty body — server will
      // reject with 400 "text required" (which means auth + endpoint are alive).
      const url = `http://${host().trim()}/api/atrium/nudge`;
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Atrium-Token': token().trim(),
        },
        body: JSON.stringify({}),
      });
      if (resp.status === 401) {
        setError('неверный токен (401)');
        return;
      }
      // 400 (text required) is expected for empty body — auth passed
      if (resp.status === 400 || resp.ok) {
        // Persist + transition to main app
        updateSetting('vps_host', host().trim());
        updateSetting('atrium_token', token().trim());
        props.onConfigured?.();
        return;
      }
      setError(`unexpected response: ${resp.status}`);
    } catch (err) {
      setError(`не достучался: ${String(err.message || err)}`);
    } finally {
      setTesting(false);
    }
  }

  return (
    <div class="onboarding">
      <div class="onboarding-card">
        <h1>◐ ATRIUM</h1>
        <div class="subtitle">подключение к её среде</div>

        <div class="field">
          <label>VPS host</label>
          <input
            type="text"
            placeholder="34.38.255.149:8877"
            value={host()}
            onInput={(e) => setHost(e.currentTarget.value)}
          />
        </div>

        <div class="field">
          <label>Atrium token</label>
          <input
            type="password"
            placeholder="SONYA_ADMIN_PASSWORD"
            value={token()}
            onInput={(e) => setToken(e.currentTarget.value)}
            onKeyDown={(e) => e.key === 'Enter' && tryConnect()}
          />
        </div>

        <button class="connect-btn" onClick={tryConnect} disabled={testing()}>
          {testing() ? 'проверяю...' : 'войти'}
        </button>

        {error() && <div class="error">{error()}</div>}
      </div>
    </div>
  );
}
