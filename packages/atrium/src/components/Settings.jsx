/* Settings modal — Connection / Notifications / Privacy. */
import { createSignal, createEffect, For, Show } from 'solid-js';
import { settings, updateSetting } from '../store.js';
import { connectWS, disconnectWS } from '../ws.js';
import { probeLocalTTS, listLocalVoices, speakText, stopVoice } from '../voice.js';

export default function Settings(props) {
  const [host, setHost] = createSignal(settings.vps_host || '');
  const [token, setToken] = createSignal(settings.atrium_token || '');
  const [avatarUrl, setAvatarUrl] = createSignal(settings.avatar_model_url || '');
  const [roomUrl, setRoomUrl] = createSignal(settings.room_model_url || '');
  const [voiceMode, setVoiceMode] = createSignal(settings.voice_mode || 'off');
  const [ttsUrl, setTtsUrl] = createSignal(settings.tts_url || 'http://127.0.0.1:8878');
  const [ttsVoice, setTtsVoice] = createSignal(settings.tts_voice || 'baya');
  const [ttsHealth, setTtsHealth] = createSignal('');
  const [ttsVoices, setTtsVoices] = createSignal([]);

  // Probe the local TTS service automatically when local/cloned is selected.
  createEffect(async () => {
    const m = voiceMode();
    if (m === 'local' || m === 'cloned') {
      // Persist tts_url first so probeLocalTTS reads the latest.
      const prev = settings.tts_url;
      if (prev !== ttsUrl().trim()) updateSetting('tts_url', ttsUrl().trim());
      setTtsHealth('проверяю…');
      const h = await probeLocalTTS();
      if (h.ok) {
        setTtsHealth(`✓ ${h.info?.model || 'ok'} (warm: ${h.info?.warm ? 'yes' : 'no'})`);
        const v = await listLocalVoices();
        setTtsVoices(v);
      } else {
        setTtsHealth(`✗ ${h.error}. Запусти services\\tts\\start_tts.ps1`);
        setTtsVoices([]);
      }
    } else {
      setTtsHealth('');
    }
  });

  function save() {
    const newHost = host().trim();
    const newToken = token().trim();
    const changed = newHost !== settings.vps_host || newToken !== settings.atrium_token;
    updateSetting('avatar_model_url', avatarUrl().trim());
    updateSetting('room_model_url', roomUrl().trim());
    updateSetting('voice_mode', voiceMode());
    updateSetting('tts_url', ttsUrl().trim());
    updateSetting('tts_voice', ttsVoice());
    if (changed) {
      updateSetting('vps_host', newHost);
      updateSetting('atrium_token', newToken);
      disconnectWS();
      setTimeout(() => connectWS(), 100);
    }
    props.onClose?.();
  }

  async function testVoice() {
    // Persist current selections so speakText reads them.
    updateSetting('voice_mode', voiceMode());
    updateSetting('tts_url', ttsUrl().trim());
    updateSetting('tts_voice', ttsVoice());
    stopVoice();
    speakText('Привет. Это проверка голоса. Меня слышно?');
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
          <label>avatar model (vrm)</label>
          <input
            type="text"
            value={avatarUrl()}
            placeholder="/models/sonya.vrm"
            onInput={(e) => setAvatarUrl(e.currentTarget.value)}
          />
          <span style="margin-left: 0; color: var(--ink-3); font-size: 12px;">
            путь к .vrm (применится при следующем открытии)
          </span>
        </div>

        <div class="modal-section">
          <label>room model (glb, опц.)</label>
          <input
            type="text"
            value={roomUrl()}
            placeholder="пусто = процедурная комната"
            onInput={(e) => setRoomUrl(e.currentTarget.value)}
          />
          <span style="margin-left: 0; color: var(--ink-3); font-size: 12px;">
            свой 3D-room .glb/.gltf (если есть) — иначе встроенная сцена
          </span>
        </div>

        <div class="modal-section">
          <label>voice (озвучка её ответов)</label>
          <select
            value={voiceMode()}
            onChange={(e) => setVoiceMode(e.currentTarget.value)}
            style="padding: 8px; background: var(--bg-elev); border: 1px solid var(--hairline); color: var(--ink-1); border-radius: 4px;"
          >
            <option value="off">off (молча)</option>
            <option value="browser">browser (бесплатный TTS ОС, ru-RU — для теста)</option>
            <option value="local">local (Silero v4_ru, локальный сервис — рекомендую)</option>
            <option value="cloned" disabled>cloned (XTTS-v2 её голос — позже)</option>
          </select>
          <span style="display:block; margin-top:6px; color: var(--ink-3); font-size: 12px;">
            browser → ритм по boundary events. local/cloned → реальная амплитуда WAV.
          </span>
        </div>

        <Show when={voiceMode() === 'local' || voiceMode() === 'cloned'}>
          <div class="modal-section">
            <label>tts service url</label>
            <input
              type="text"
              value={ttsUrl()}
              placeholder="http://127.0.0.1:8878"
              onInput={(e) => setTtsUrl(e.currentTarget.value)}
            />
            <span style="display:block; margin-top:6px; color: var(--ink-3); font-size: 12px;">
              Сервис из <code>services\tts\</code>. Запусти: <code>services\tts\start_tts.ps1</code>.
            </span>
            <span style="display:block; margin-top:4px; font-size: 12px;"
                  classList={{
                    'tts-health-ok': ttsHealth().startsWith('✓'),
                    'tts-health-err': ttsHealth().startsWith('✗'),
                    'tts-health-pending': ttsHealth() === 'проверяю…',
                  }}>
              {ttsHealth() || ' '}
            </span>
          </div>

          <Show when={ttsVoices().length > 0}>
            <div class="modal-section">
              <label>tts voice</label>
              <select
                value={ttsVoice()}
                onChange={(e) => setTtsVoice(e.currentTarget.value)}
                style="padding: 8px; background: var(--bg-elev); border: 1px solid var(--hairline); color: var(--ink-1); border-radius: 4px;"
              >
                <For each={ttsVoices()}>
                  {(v) => <option value={v}>{v}</option>}
                </For>
              </select>
              <span style="display:block; margin-top:6px; color: var(--ink-3); font-size: 12px;">
                Silero RU: baya/kseniya/xenia (ж), aidar/eugene (м).
              </span>
            </div>
          </Show>
        </Show>

        <Show when={voiceMode() !== 'off'}>
          <div class="modal-section">
            <button class="primary" type="button" onClick={testVoice}>▶ test voice</button>
            <span style="margin-left: 10px; color: var(--ink-3); font-size: 12px;">
              скажет «Привет. Это проверка голоса.»
            </span>
          </div>
        </Show>

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
