import { feed, settings } from '../store.js';

export default function Header(props) {
  return (
    <header class="header">
      <span class="logo">◐ ATRIUM</span>
      <span class="spacer"></span>
      <span class="conn">
        <span
          classList={{
            'conn-dot': true,
            disconnected: !feed.connected,
          }}
        />
        {feed.connected
          ? `connected · ${settings.vps_host}`
          : feed.reconnecting
          ? 'reconnecting...'
          : feed.last_error || 'disconnected'}
      </span>
      <button class="menu-btn" title="settings" onClick={props.onOpenSettings}>
        ⋮
      </button>
    </header>
  );
}
