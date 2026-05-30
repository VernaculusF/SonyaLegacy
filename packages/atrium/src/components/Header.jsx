import { feed, settings } from '../store.js';

export default function Header(props) {
  return (
    <header class="header">
      <span class="logo">SONYA</span>
      <span class="header-sub">atrium</span>
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
      <button class="icon-btn" title="консоль (операторка, задачи, репозиторий)" onClick={props.onOpenConsole}>
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none">
          <rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" stroke-width="1.6" />
          <path d="M7 9l3 3-3 3M13 15h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <button class="icon-btn" title="workshop (skills/tools/packages/repo)" onClick={props.onOpenWorkshop}>
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none">
          <path d="M11 4a4 4 0 015.5 5.2l4 4a1.5 1.5 0 01-2.1 2.1l-4-4A4 4 0 0111 4z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
          <path d="M9.5 9.5L4 15v3h3l5.5-5.5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
        </svg>
      </button>
      <button class="icon-btn" title="настройки" onClick={props.onOpenSettings}>
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none">
          <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6" />
          <path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        </svg>
      </button>
    </header>
  );
}
