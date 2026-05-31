/* Native Windows toast notifications via tauri-plugin-notification.
 *
 * Триггеры:
 *   1. Atrium свёрнут или потерял focus (document.hidden) — показываем toast
 *      на каждое исходящее dialog-сообщение от Сони. Иван видит уведомление
 *      даже когда окно не на экране.
 *   2. NEVER notify когда окно сфокусировано — Иван и так видит сообщение.
 *
 * Permission flow:
 *   - At startup, ws.js → ensureNotificationPermission()
 *   - First run: запрашивает у пользователя
 *   - Subsequent: silent
 *   - If denied: гасим всё silently — приложение работает без toast'ов.
 *
 * Web fallback: если @tauri-apps/plugin-notification не доступен (запуск
 * Atrium как vite в браузере для разработки), используем Notification API
 * браузера. Identical UX в нашем случае.
 */

let _granted = null; // null=unknown, true=ok, false=denied
let _api = null;     // 'tauri' | 'web' | null

async function _loadTauriApi() {
  try {
    const mod = await import('@tauri-apps/plugin-notification');
    return mod;
  } catch {
    return null;
  }
}

export async function ensureNotificationPermission() {
  if (_granted !== null) return _granted;

  const tauri = await _loadTauriApi();
  if (tauri) {
    _api = 'tauri';
    try {
      let granted = await tauri.isPermissionGranted();
      if (!granted) {
        const perm = await tauri.requestPermission();
        granted = perm === 'granted';
      }
      _granted = granted;
      return granted;
    } catch (e) {
      _granted = false;
      return false;
    }
  }

  // Web fallback
  if (typeof Notification !== 'undefined') {
    _api = 'web';
    if (Notification.permission === 'granted') {
      _granted = true;
    } else if (Notification.permission === 'denied') {
      _granted = false;
    } else {
      try {
        const perm = await Notification.requestPermission();
        _granted = perm === 'granted';
      } catch {
        _granted = false;
      }
    }
    return _granted;
  }

  _granted = false;
  return false;
}

export async function notify({ title, body, sound = true }) {
  if (!_granted) return;
  // Don't notify when the window is visible/focused — user is looking.
  if (typeof document !== 'undefined' && !document.hidden) return;

  if (_api === 'tauri') {
    try {
      const tauri = await _loadTauriApi();
      if (tauri) {
        await tauri.sendNotification({
          title: title || 'Соня',
          body: body || '',
          sound: sound ? 'default' : null,
        });
      }
    } catch {
      // best-effort
    }
    return;
  }

  if (_api === 'web' && typeof Notification !== 'undefined') {
    try {
      // eslint-disable-next-line no-new
      new Notification(title || 'Соня', { body: body || '', silent: !sound });
    } catch {
      // best-effort
    }
  }
}
