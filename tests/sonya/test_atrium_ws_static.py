from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_atrium_ws_uses_ephemeral_ticket_not_admin_token_query() -> None:
    source = (ROOT / "packages/atrium/src/ws.js").read_text(encoding="utf-8")

    assert "requestWsTicket" in source
    assert "/api/atrium/ws-ticket" in source
    assert "ticket=${encodeURIComponent(ticket)}" in source
    assert "&token=${encodeURIComponent(settings.atrium_token)}" not in source
    assert "?token=${encodeURIComponent(settings.atrium_token)}" not in source
