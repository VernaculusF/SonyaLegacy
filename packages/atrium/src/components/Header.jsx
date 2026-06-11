import { feed, settings, activeWorkspaceId, switchWorkspace } from '../store.js';
import { Show } from 'solid-js';

export default function Header(props) {
  return (
    <header class="header">
      <div class="header-left">
        <span class="logo">SONYA</span>
        <span class="header-sub">atrium</span>
      </div>

      <button class="icon-btn projects-btn" onClick={props.onToggleProjects} title="Проекты">
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.6">
          <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
        </svg>
      </button>

      <Show when={activeWorkspaceId() !== 'main'}>
        <button class="icon-btn home-btn" onClick={() => switchWorkspace('main')} title="Основной чат">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
        </button>
      </Show>

      <span class="spacer"></span>
      <span class="conn" title={feed.connected ? settings.vps_host : (feed.last_error || '')}>
        <span
          classList={{
            'conn-dot': true,
            disconnected: !feed.connected,
          }}
        />
        {feed.connected
          ? 'на связи'
          : feed.reconnecting
          ? 'соединение…'
          : 'нет связи'}
      </span>
      <button class="inner-stream-btn" title="inner stream / reason logs" onClick={props.onOpenReasonStream}>
        inner
      </button>
      <button class="icon-btn" title="консоль (операторка, задачи, репозиторий)" onClick={props.onOpenConsole}>
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none">
          <rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" stroke-width="1.6" />
          <path d="M8 12l2 2 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <button class="icon-btn" title="workshop (skills/tools/packages/repo)" onClick={props.onOpenWorkshop}>
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none">
          <path d="M11 4a4 4 0 015.5 5.2l4 4a1.5 1.5 0 01-2.1 2.1l-4-4A4 4 0 0111 4z" stroke="currentColor" stroke-width="1.6" />
          <path d="M9 10l-5 5a2 2 0 002.8 2.8l5-5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
        </svg>
      </button>
      <button class="icon-btn" title="настройки" onClick={props.onOpenSettings}>
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none">
          <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6" />
          <path d="M12 3v2m0 14v2m-9-9h2m14 0h2M5.6 5.6l1.4 1.4m10 10l1.4 1.4m-1.4-12l1.4-1.4M7 17l-1.4 1.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        </svg>
      </button>
    </header>
  );
}
