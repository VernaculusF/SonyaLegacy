/* Settings modal — Connection / Notifications / Privacy. */
import { createSignal, createEffect, For, Show } from 'solid-js';
import { settings, updateSetting } from '../store.js';
import { connectWS, disconnectWS } from '../ws.js';
import { probeLocalTTS, listLocalVoices, probeElevenLabs, speakText, stopVoice } from '../voice.js';

export default function Settings(props) {
  const [host, setHost] = createSignal(settings.vps_host || '');
  const [token, setToken] = createSignal(settings.atrium_token || '');
  const [avatarUrl, setAvatarUrl] = createSignal(settings.avatar_model_url || '');
  const [roomUrl, setRoomUrl] = createSignal(settings.room_model_url || '');
  const [voiceMode, setVoiceMode] = createSignal(settings.voice_mode || 'off');
  const [ttsUrl, setTtsUrl] = createSignal(settings.tts_url || 'http://127.0.0.1:8878');
  const [ttsVoice, setTtsVoice] = createSignal(settings.tts_voice || 'irina');
  const [ttsVoiceId, setTtsVoiceId] = createSignal(settings.tts_voice_id || 'pFZP5JQG7iQjIQuC4Bku');
  const [ttsModelId, setTtsModelId] = createSignal(settings.tts_model_id || 'eleven_multilingual_v2');
  const [ttsHealth, setTtsHealth] = createSignal('');
  const [ttsVoices, setTtsVoices] = createSignal([]);

  // Probe whichever TTS path is selected.
  createEffect(async () => {
    const m = voiceMode();
    if (m === 'local') {
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
    } else if (m === 'elevenlabs') {
      setTtsHealth('проверяю…');
      const h = await probeElevenLabs();
      if (h.ok && h.info) {
        const used = h.info.char_count ?? '?';
        const lim = h.info.char_limit ?? '?';
        const tier = h.info.tier ? `${h.info.tier} · ` : '';
        setTtsHealth(`✓ elevenlabs · ${tier}${used}/${lim} chars used`);
      } else {
        setTtsHealth(`✗ ${h.error || 'недоступно'}`);
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
    updateSetting('tts_voice_id', ttsVoiceId().trim());
    updateSetting('tts_model_id', ttsModelId().trim());
    if (changed) {
      updateSetting('vps_host', newHost);
      updateSetting('atrium_token', newToken);
      disconnectWS();
      setTimeout(() => connectWS(), 100);
    }
    props.onClose?.();
  }

  async function testVoice() {
    updateSetting('voice_mode', voiceMode());
    updateSetting('tts_url', ttsUrl().trim());
    updateSetting('tts_voice', ttsVoice());
    updateSetting('tts_voice_id', ttsVoiceId().trim());
    updateSetting('tts_model_id', ttsModelId().trim());
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
            <option value="browser">browser (системный TTS — для теста)</option>
            <option value="local">local (Piper Irina, бесплатно — посредственно)</option>
            <option value="elevenlabs">elevenlabs (топ качество — твой voice id)</option>
          </select>
          <span style="display:block; margin-top:6px; color: var(--ink-3); font-size: 12px;">
            elevenlabs идёт через VPS-прокси (ключ только на сервере). free tier 10K симв/мес.
          </span>
        </div>

        <Show when={voiceMode() === 'elevenlabs'}>
          <div class="modal-section">
            <label>elevenlabs voice</label>
            <select
              value={ttsVoiceId()}
              onChange={(e) => setTtsVoiceId(e.currentTarget.value)}
              style="padding: 8px; background: var(--bg-elev); border: 1px solid var(--hairline); color: var(--ink-1); border-radius: 4px;"
            >
              <optgroup label="default voices (free tier ok)">
                <option value="pFZP5JQG7iQjIQuC4Bku">Lily — warm female (рекомендую)</option>
                <option value="EXAVITQu4vr4xnSDxMaL">Sarah — soft female</option>
                <option value="XrExE9yKIg1WjnnlVkGX">Matilda — friendly young</option>
                <option value="cgSgspJ2msm6clMCkdW9">Jessica — conversational female</option>
                <option value="FGY2WhTYpPnrIDTdsKH5">Laura — sunny young</option>
                <option value="Xb7hH8MSUJpSbSDYk0k2">Alice — confident british</option>
                <option value="SAz9YHcvj6GT2YYXdXww">River — calm female</option>
                <option value="JBFqnCBsd6RMkjVDRZzb">George — male</option>
                <option value="onwK4e9ZLuTAKqWW03F9">Daniel — narrative male</option>
                <option value="iP95p4xoKVk53GoZ742B">Chris — casual male</option>
              </optgroup>
              <optgroup label="custom (paid plan для voice library)">
                <option value="custom">— ввести свой voice id —</option>
              </optgroup>
            </select>
            <span style="display:block; margin-top:6px; color: var(--ink-3); font-size: 12px;">
              Free tier API даёт только default voices. Для voice library нужна подписка $5+/мес.
            </span>
          </div>
          <Show when={ttsVoiceId() === 'custom'}>
            <div class="modal-section">
              <label>custom voice id</label>
              <input
                type="text"
                placeholder="0ArNnoIAWKlT4WweaVMY"
                onInput={(e) => setTtsVoiceId(e.currentTarget.value)}
              />
            </div>
          </Show>
          <div class="modal-section">
            <label>elevenlabs model</label>
            <select
              value={ttsModelId()}
              onChange={(e) => setTtsModelId(e.currentTarget.value)}
              style="padding: 8px; background: var(--bg-elev); border: 1px solid var(--hairline); color: var(--ink-1); border-radius: 4px;"
            >
              <option value="eleven_multilingual_v2">multilingual v2 (best, RU)</option>
              <option value="eleven_turbo_v2_5">turbo v2.5 (faster, slightly less natural)</option>
              <option value="eleven_flash_v2_5">flash v2.5 (~75ms latency)</option>
            </select>
            <span style="display:block; margin-top:4px; font-size: 12px;"
                  classList={{
                    'tts-health-ok': ttsHealth().startsWith('✓'),
                    'tts-health-err': ttsHealth().startsWith('✗'),
                    'tts-health-pending': ttsHealth() === 'проверяю…',
                  }}>
              {ttsHealth() || ' '}
            </span>
          </div>
        </Show>

        <Show when={voiceMode() === 'local'}>
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
                Piper RU: irina (ж), denis/ruslan (м).
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
