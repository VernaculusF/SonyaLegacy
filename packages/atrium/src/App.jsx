/* Atrium root — handles onboarding gate vs main app shell.
 * См. UX_SKETCH.md §5 для desktop layout.
 */
import { Show, createSignal, onMount, onCleanup } from 'solid-js';
import { settings, feed, updateSetting } from './store.js';
import { connectWS, disconnectWS, startHeartbeat, stopHeartbeat } from './ws.js';
import { stopVoice } from './voice.js';
import Onboarding from './components/Onboarding.jsx';
import Header from './components/Header.jsx';
import AvatarPane from './components/AvatarPane.jsx';
import DialogPane from './components/DialogPane.jsx';
import MindPane from './components/MindPane.jsx';
import ReasonStream from './components/ReasonStream.jsx';
import Settings from './components/Settings.jsx';
import RoomView from './components/RoomView.jsx';
import Workshop from './components/Workshop.jsx';

export default function App() {
  const [showSettings, setShowSettings] = createSignal(false);
  const [showRoom, setShowRoom] = createSignal(false);
  const [showWorkshop, setShowWorkshop] = createSignal(false);

  // Onboarding done if both fields are set
  const isConfigured = () => Boolean(settings.vps_host && settings.atrium_token);

  // Connect on mount if configured
  onMount(() => {
    if (isConfigured()) {
      connectWS();
      startHeartbeat();
    }
    // Keyboard: Ctrl+J / Cmd+J → toggle reason-stream collapse
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        updateSetting('streams_collapsed', !settings.streams_collapsed);
      }
    };
    window.addEventListener('keydown', onKey);
    // Stop her voice when the tab goes to background (so she doesn't keep
    // talking when Ivan switched away).
    const onVis = () => { if (document.hidden) stopVoice(); };
    document.addEventListener('visibilitychange', onVis);
    onCleanup(() => {
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('visibilitychange', onVis);
      stopVoice();
      disconnectWS();
      stopHeartbeat();
    });
  });

  return (
    <Show
      when={isConfigured()}
      fallback={
        <Onboarding
          onConfigured={() => {
            connectWS();
            startHeartbeat();
          }}
        />
      }
    >
      <div
        classList={{
          app: true,
          'streams-collapsed': settings.streams_collapsed,
        }}
      >
        <Header onOpenSettings={() => setShowSettings(true)} onOpenWorkshop={() => setShowWorkshop(true)} />

        <div class="main">
          <AvatarPane onEnterRoom={() => setShowRoom(true)} />
          <DialogPane onEnterRoom={() => setShowRoom(true)} />
          <MindPane />
        </div>

        <ReasonStream />

        <Show when={showSettings()}>
          <Settings onClose={() => setShowSettings(false)} />
        </Show>

        <Show when={showRoom()}>
          <RoomView onClose={() => setShowRoom(false)} />
        </Show>

        <Show when={showWorkshop()}>
          <Workshop onClose={() => setShowWorkshop(false)} />
        </Show>
      </div>
    </Show>
  );
}
