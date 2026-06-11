import { Show, createSignal, onMount, onCleanup } from 'solid-js';
import { settings, feed, updateSetting, activeWorkspaceId, fetchProjects, fetchEvolutionPressure } from './store.js';
import { connectWS, disconnectWS, startHeartbeat, stopHeartbeat } from './ws.js';
import Onboarding from './components/Onboarding.jsx';
import Header from './components/Header.jsx';
import ChatSidebar from './components/ChatSidebar.jsx';
import AvatarPane from './components/AvatarPane.jsx';
import DialogPane from './components/DialogPane.jsx';
import ProjectWorkspace from './components/ProjectWorkspace.jsx';
import MindPane from './components/MindPane.jsx';
import ReasonStream from './components/ReasonStream.jsx';
import Settings from './components/Settings.jsx';
import RoomView from './components/RoomView.jsx';
import Workshop from './components/Workshop.jsx';
import Console from './components/Console.jsx';

export default function App() {
  const [showSettings, setShowSettings] = createSignal(false);
  const [showRoom, setShowRoom] = createSignal(false);
  const [showWorkshop, setShowWorkshop] = createSignal(false);
  const [showConsole, setShowConsole] = createSignal(false);
  const [showChats, setShowChats] = createSignal(false);
  const [showReasonStream, setShowReasonStream] = createSignal(false);

  const isConfigured = () => Boolean(settings.vps_host && settings.atrium_token);

  onMount(() => {
    if (isConfigured()) {
      connectWS();
      startHeartbeat();
      fetchProjects();
      fetchEvolutionPressure();
    }
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        updateSetting('streams_collapsed', !settings.streams_collapsed);
      }
    };
    window.addEventListener('keydown', onKey);
    const onVis = () => {
      document.documentElement.classList.toggle('app-hidden', document.hidden);
    };
    document.addEventListener('visibilitychange', onVis);
    onVis();
    onCleanup(() => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('visibilitychange', onVis);
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
        <Header
          onToggleProjects={() => setShowChats((value) => !value)}
          onOpenSettings={() => setShowSettings(true)}
          onOpenWorkshop={() => setShowWorkshop(true)}
          onOpenConsole={() => setShowConsole(true)}
          onOpenReasonStream={() => setShowReasonStream(true)}
        />

        <ChatSidebar open={showChats} onClose={() => setShowChats(false)} />

        <div class="main">
          <AvatarPane onEnterRoom={() => setShowRoom(true)} />
          <DialogPane onEnterRoom={() => setShowRoom(true)} />
          <Show
            when={activeWorkspaceId() !== 'main'}
            fallback={<MindPane />}
          >
            <ProjectWorkspace
              onEnterRoom={() => setShowRoom(true)}
              onOpenWorkshop={() => setShowWorkshop(true)}
            />
          </Show>
        </div>

        <Show when={showReasonStream()}>
          <ReasonStream onClose={() => setShowReasonStream(false)} />
        </Show>

        <Show when={showSettings()}>
          <Settings onClose={() => setShowSettings(false)} />
        </Show>

        <Show when={showRoom()}>
          <RoomView onClose={() => setShowRoom(false)} />
        </Show>

        <Show when={showWorkshop()}>
          <Workshop onClose={() => setShowWorkshop(false)} />
        </Show>

        <Show when={showConsole()}>
          <Console onClose={() => setShowConsole(false)} />
        </Show>
      </div>
    </Show>
  );
}
