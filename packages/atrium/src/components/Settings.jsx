/* Settings modal — Connection / Notifications / Privacy. */
import { createSignal } from 'solid-js';
import { settings, updateSetting } from '../store.js';
import { connectWS, disconnectWS } from '../ws.js';

export default function Settings(props) {
  const [host, setHost] = createSignal(settings.vps_host || '');
  const [token, setToken] = createSignal(settings.atrium_token || '');

  function save() {
    const newHost = host().trim();
    const newToken = token().trim();
    const changed = newHost !== settings.vps_host || newToken !== settings.atrium_token;
    if (changed) {
      updateSetting('vps_host', newHost);
      updateSetting('atrium_token', newToken);
      // Reconnect with new credentials
      disconnectWS();
      setTimeout(() => connectWS(), 100);
    }
    props.onClose?.();
  }

  return (
    <div class="modal-overlay" onClick={(e) => e.target === e.currentTarget && props.onClose?.()}>
      <div class="modal">
        <h2>SETTINGS</h2>

        <div class="modal-section">
          <label>vps host</label>
          <input
            type="text"
            value={host()}
            onInput={(e) => setHost(e.currentTarget.value)}
          />
        </div>

        <div class="modal-section">
          <label>atrium token</label>
          <input
            type="password"
            value={token()}
            onInput={(e) => setToken(e.currentTarget.value)}
          />
        </div>

        <div class="modal-section">
          <label>show private aggregate count</label>
          <input
            type="checkbox"
            checked={settings.show_private_count}
            onChange={(e) => updateSetting('show_private_count', e.currentTarget.checked)}
          />
          <span style="margin-left: 8px; color: var(--ink-3); font-size: 12px;">
            показывать "(N private thoughts hidden)" в Mind pane
          </span>
        </div>

        <div class="modal-section">
          <label>dialog notifications</label>
          <select
            value={settings.notifications_dialog}
            onChange={(e) => updateSetting('notifications_dialog', e.currentTarget.value)}
            style="padding: 8px; background: var(--bg-elev); border: 1px solid var(--hairline); color: var(--ink-1); border-radius: 4px;"
          >
            <option value="full">full (chime + glow)</option>
            <option value="quiet">quiet (только icon glow)</option>
            <option value="off">off</option>
          </select>
        </div>

        <div class="modal-actions">
          <button onClick={props.onClose}>cancel</button>
          <button class="primary" onClick={save}>
            save
          </button>
        </div>
      </div>
    </div>
  );
}
