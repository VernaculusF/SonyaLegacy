/* Mind pane: focus + drives + env + inner stream + private aggregate.
 * Updates via meta-messages every 60s + immediate on mind.* events.
 */
import { For, Show } from 'solid-js';
import { feed, settings } from '../store.js';

const DRIVE_ORDER = ['curiosity', 'relational_focus', 'pending_debt', 'boredom'];

const DRIVE_LABEL = {
  curiosity: 'curiosity',
  relational_focus: 'attachment', // human-readable label for Иван
  pending_debt: 'pending_debt',
  boredom: 'boredom',
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
        <h2>FOCUS</h2>
        <div classList={{ 'mind-focus': true, empty: !feed.current_focus }}>
          {feed.current_focus || 'нет фокуса'}
        </div>
      </div>

      <div class="mind-section">
        <h2>DRIVES</h2>
        <div class="drives">
          <For each={DRIVE_ORDER}>
            {(key) => <DriveBar label={DRIVE_LABEL[key]} value={feed.drives[key] ?? 0} />}
          </For>
        </div>
      </div>

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

      <Show when={feed.inner_thoughts.length > 0 || (settings.show_private_count && feed.private_count_last_hour > 0)}>
        <div class="stream-divider">inner stream</div>

        <Show when={settings.show_private_count && feed.private_count_last_hour > 0}>
          <div class="thought private">
            <div class="age">last hour</div>
            <div class="body">
              ({feed.private_count_last_hour} private thoughts hidden)
            </div>
          </div>
        </Show>

        <For each={feed.inner_thoughts}>
          {(t) => (
            <div classList={{ thought: true, private: t.private }}>
              <div class="age">{t.age}</div>
              <div class="body">{t.text}</div>
            </div>
          )}
        </For>
      </Show>
    </aside>
  );
}
