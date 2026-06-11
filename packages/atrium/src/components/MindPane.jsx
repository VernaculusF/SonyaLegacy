/* Mind pane: presence + focus + drives + env + inner stream + private aggregate.
 * Updates via meta-messages every 60s + immediate on mind.* events.
 */
import { For, Show } from 'solid-js';
import { feed, speaking } from '../store.js';

const EXPRESSION_LABEL = {
  neutral: 'спокойна',
  smile: 'улыбается',
  thinking: 'задумалась',
  tired: 'устала',
  sad: 'грустная',
  sad_tears: 'плачет',
  excited: 'оживлена',
  curious: 'любопытно',
  tender: 'нежная',
  annoyed: 'раздражена',
  angry: 'злится',
  shy: 'смущена',
  desire: 'желание',
  playful: 'игривая',
  calm: 'умиротворена',
  surprised: 'удивлена',
  joy: 'радуется',
};

function DriveBar(props) {
  const segments = 10;
  const filled = () => Math.min(segments, Math.max(0, Math.round((props.value || 0) * segments)));
  return (
    <div class="drive">
      <span class="drive-label">{props.label}</span>
      <div class="drive-bar">
        <For each={Array.from({ length: segments }, (_, i) => i)}>
          {(i) => (
            <div
              classList={{
                'drive-seg': true,
                on: i < filled(),
                peak: i === filled() - 1,
              }}
            />
          )}
        </For>
      </div>
      <span class="drive-val">{(props.value || 0).toFixed(2)}</span>
    </div>
  );
}

export default function MindPane() {
  return (
    <aside class="pane right">
      <div class="mind-section">
        <h2>PRESENCE</h2>
        <div class="presence-lines">
          <div class="status-line">
            <span class="label">смотрит</span>
            ивана
          </div>
          <div class="status-line">
            <span class="label">воспринимает</span>
            {feed.her_typing ? 'печатает' : speaking() ? 'говорит' : 'тишина'}
          </div>
          <div class="status-line">
            <span class="label">чувствует</span>
            {EXPRESSION_LABEL[feed.current_expression] || feed.current_expression}
          </div>
          <Show when={feed.her_typing}>
            <div class="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </Show>
        </div>
      </div>

      <div class="mind-section">
        <h2>FOCUS</h2>
        <div classList={{ 'mind-focus': true, empty: !feed.current_focus }}>
          {feed.current_focus || 'нет фокуса'}
        </div>
      </div>

      <Show when={feed.evolution_pressure.length > 0}>
        <div class="mind-section">
          <h2>EVOLUTION PRESSURE</h2>
          <div class="drives">
            <For each={feed.evolution_pressure}>
              {(dim) => <DriveBar label={dim.dimension} value={dim.gap ?? 0} />}
            </For>
          </div>
        </div>
      </Show>

      <div class="mind-section">
        <h2>SUBJECT STATE</h2>
        <div class="env-table">
          <div>
            <span class="k">outfit:</span> <span class="v">{feed.current_outfit}</span>
          </div>
          <div>
            <span class="k">expression:</span> <span class="v">{feed.current_expression}</span>
          </div>
          <div>
            <span class="k">mood_tint:</span> <span class="v">{feed.mood_tint}</span>
          </div>
        </div>
      </div>

    </aside>
  );
}
