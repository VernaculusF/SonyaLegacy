from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ContinuityEvent:
    """One entry in the continuity stream. seq is assigned by the stream on append.

    v20 (Atrium Этап 0): added `channel` and `private` fields.
      - `channel`: 'dialog' | 'worker_log' | 'mind' | 'body' | 'voice' | ''
        Used by /atrium/feed routing. Mirrored to continuity_events.channel
        column (SQL-level filtering без парсинга payload).
      - `private`: True → событие сохраняется в substrate (audit/recall/identity
        видят полный feed) but NOT отдаётся через /atrium/feed. Реализация
        right_to_inner_privacy (5-й столп things_not_to_betray).
    См. docs/atrium/EVENT_SCHEMA.md §6.
    """

    kind: str
    principal_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    channel: str = ""
    private: bool = False
    seq: int = 0
    created_at: str = ""


class ContinuityStream:
    """Append-only event log over substrate."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def append(self, event: ContinuityEvent) -> ContinuityEvent:
        now = _utc_now_iso()
        # `channel` and `private` are mirrored from event into dedicated columns
        # so /atrium/feed can filter at SQL layer без парсинга payload_json.
        # Backward-compat: also fall back to payload values if event-level
        # fields are not set (callers in pre-v20 code не знали про channel).
        channel = event.channel or (event.payload.get("channel") if isinstance(event.payload, dict) else "") or ""
        private_val = event.private
        if not private_val and isinstance(event.payload, dict):
            private_val = bool(event.payload.get("private", False))
        cursor = self._sub.connection.execute(
            "INSERT INTO continuity_events("
            "kind, principal_id, payload_json, channel, private, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.kind,
                event.principal_id,
                json.dumps(event.payload, ensure_ascii=False),
                str(channel),
                1 if private_val else 0,
                now,
            ),
        )
        self._sub.connection.commit()
        seq = cursor.lastrowid or 0
        appended = ContinuityEvent(
            kind=event.kind,
            principal_id=event.principal_id,
            payload=event.payload,
            channel=str(channel),
            private=bool(private_val),
            seq=int(seq),
            created_at=now,
        )

        # Expression auto-derive hook.
        #
        # Wyrazenie лица — состояние тела, не tool call. См.
        # docs/atrium/EXPRESSION_AS_STATE.md. На каждый dialog turn
        # (входящий от Ивана + исходящий от Сони) мы запускаем дешёвую
        # эвристику и обновляем `subject_state.current_expression` если
        # классификатор уверен. Heuristic miss → выражение не трогаем.
        # Чтобы не зацикливаться, hook игнорирует свои же
        # `outgoing.body_expression` события.
        try:
            self._maybe_derive_expression(appended)
        except Exception:
            # Hook is best-effort. Crash здесь не должен ломать append.
            pass

        return appended

    # Kinds на которые срабатывает auto-derive. Текстовые dialog turns —
    # реакция Сони на вход Ивана и отражение тона её ответа.
    _DERIVE_KINDS_INCOMING = frozenset({
        "incoming.atrium_dialog",
        "incoming.telegram_message",
    })
    _DERIVE_KINDS_OUTGOING = frozenset({
        "outgoing.dialog",
        "outgoing.telegram_response",
        "outgoing.telegram_initiative",
        "outgoing.telegram_progress",
        "outgoing.response",
    })

    def _maybe_derive_expression(self, event: ContinuityEvent) -> None:
        """Run expression classifier on dialog turns; update subject_state.

        Only fires on a small set of kinds (text-bearing dialog events).
        Heuristic-only — Phase 1. LLM fallback может позже добавить
        отдельный async worker, но из stream.append синхронно мы LLM
        не вызываем (nonzero latency).
        """
        kind = event.kind
        if kind not in self._DERIVE_KINDS_INCOMING and kind not in self._DERIVE_KINDS_OUTGOING:
            return
        payload = event.payload if isinstance(event.payload, dict) else {}
        text = (payload.get("text") or "").strip()
        if not text:
            return
        # Don't run on ourselves.
        if kind == "outgoing.body_expression":
            return

        # Lazy import — classifier is in state layer (same layer as us)
        # to keep `state` self-contained (no upward dep on subject).
        try:
            from sonya.state.expression_classifier import classify, DEFAULT
        except Exception:
            return

        role = "him" if kind in self._DERIVE_KINDS_INCOMING else "her"
        result = classify(text, role=role)
        # Only update when heuristic actually matched something.
        # confidence < 0.5 → DEFAULT marker, не трогаем текущее выражение.
        if result.confidence < 0.5:
            return
        new_marker = result.marker
        if not new_marker or new_marker == DEFAULT:
            return

        # Read current expression to skip no-op writes.
        try:
            row = self._sub.connection.execute(
                "SELECT current_expression FROM subject_state WHERE id = 1"
            ).fetchone()
            previous = (row[0] if row else "neutral") or "neutral"
        except Exception:
            previous = "neutral"
        if previous == new_marker:
            return

        # Update subject_state.
        try:
            self._sub.connection.execute(
                "INSERT INTO subject_state(id, current_expression, updated_at) "
                "VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "current_expression = excluded.current_expression, "
                "updated_at = excluded.updated_at",
                (new_marker, _utc_now_iso()),
            )
            self._sub.connection.commit()
        except Exception:
            return

        # Emit outgoing.body_expression event so Atrium WS picks it up live.
        # Recursive append goes through us again — but the kind isn't in
        # _DERIVE_KINDS_*, so the hook short-circuits.
        try:
            self._sub.connection.execute(
                "INSERT INTO continuity_events("
                "kind, principal_id, payload_json, channel, private, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "outgoing.body_expression",
                    None,
                    json.dumps({
                        "marker": new_marker,
                        "previous": previous,
                        "source": "auto",
                        "trigger_kind": kind,
                        "trigger_seq": event.seq,
                    }, ensure_ascii=False),
                    "body",
                    0,
                    _utc_now_iso(),
                ),
            )
            self._sub.connection.commit()
        except Exception:
            return

    def latest_seq(self) -> int:
        row = self._sub.connection.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM continuity_events"
        ).fetchone()
        return int(row[0]) if row else 0

    def read_since(self, seq: int) -> Iterator[ContinuityEvent]:
        cursor = self._sub.connection.execute(
            "SELECT seq, kind, principal_id, payload_json, channel, private, created_at "
            "FROM continuity_events WHERE seq > ? ORDER BY seq ASC",
            (seq,),
        )
        for row in cursor.fetchall():
            yield ContinuityEvent(
                seq=int(row[0]),
                kind=row[1],
                principal_id=row[2],
                payload=json.loads(row[3] or "{}"),
                channel=row[4] or "",
                private=bool(row[5]),
                created_at=row[6],
            )

    def read_since_atrium(
        self,
        seq: int,
        *,
        channel: str | None = None,
        session_id: str | None = None,
    ) -> Iterator[ContinuityEvent]:
        """Read events for /atrium/feed.

        Excludes events with private=1 by design — Sonya's right to inner
        privacy. Optional filters: channel, session_id (matches payload field).
        Substrate API (audit, identity, recall, selfmod) should use plain
        `read_since` which sees everything.
        """
        query = (
            "SELECT seq, kind, principal_id, payload_json, channel, private, created_at "
            "FROM continuity_events WHERE seq > ? AND private = 0"
        )
        params: list[object] = [seq]
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        query += " ORDER BY seq ASC"
        cursor = self._sub.connection.execute(query, params)
        for row in cursor.fetchall():
            payload = json.loads(row[3] or "{}")
            if session_id is not None and isinstance(payload, dict):
                if payload.get("session_id") != session_id:
                    continue
            yield ContinuityEvent(
                seq=int(row[0]),
                kind=row[1],
                principal_id=row[2],
                payload=payload,
                channel=row[4] or "",
                private=bool(row[5]),
                created_at=row[6],
            )

    def private_count_recent(self, hours: int = 1) -> int:
        """Count private events in last N hours. Used for meta-message in
        /atrium/feed: "(N private thoughts hidden in last hour)".

        See: docs/atrium/CHANNELS.md §3.5.
        """
        cursor = self._sub.connection.execute(
            "SELECT COUNT(*) FROM continuity_events "
            "WHERE private = 1 AND created_at > datetime('now', ?)",
            (f"-{int(hours)} hours",),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0
