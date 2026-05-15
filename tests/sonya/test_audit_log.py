from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.harness import AuditEvent, AuditLog
from sonya.state import Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_append_assigns_monotonic_seq(substrate: Substrate) -> None:
    log = AuditLog(substrate)
    a = log.append(
        principal_id="ivan",
        action="rewrite_lifecycle",
        decision="allow",
        scope="self_modification",
    )
    b = log.append(
        principal_id="ivan",
        action="open_socket",
        decision="deny",
        scope="network.outbound",
    )
    assert a.seq >= 1
    assert b.seq > a.seq


def test_append_returns_event_with_timestamp_and_metadata(
    substrate: Substrate,
) -> None:
    log = AuditLog(substrate)
    event = log.append(
        principal_id="ivan",
        action="x",
        decision="allow",
        scope="y",
        metadata={"reason": "anchor", "rule_id": 7},
    )
    assert event.timestamp
    assert event.metadata == {"reason": "anchor", "rule_id": 7}
    assert event.principal_id == "ivan"


def test_append_principal_id_can_be_none(substrate: Substrate) -> None:
    log = AuditLog(substrate)
    event = log.append(
        principal_id=None,
        action="bootstrap",
        decision="allow",
        scope="system.boot",
    )
    assert event.principal_id is None


def test_query_by_principal(substrate: Substrate) -> None:
    log = AuditLog(substrate)
    log.append(principal_id="ivan", action="a", decision="allow", scope="s1")
    log.append(principal_id="other", action="b", decision="deny", scope="s2")
    log.append(principal_id="ivan", action="c", decision="allow", scope="s3")

    rows = log.query(principal_id="ivan")
    assert [e.action for e in rows] == ["a", "c"]


def test_query_by_scope(substrate: Substrate) -> None:
    log = AuditLog(substrate)
    log.append(principal_id="ivan", action="a", decision="allow", scope="net.out")
    log.append(principal_id="ivan", action="b", decision="allow", scope="fs.write")
    log.append(principal_id="ivan", action="c", decision="deny", scope="net.out")

    rows = log.query(scope="net.out")
    assert [e.action for e in rows] == ["a", "c"]


def test_query_by_time_range(substrate: Substrate) -> None:
    log = AuditLog(substrate)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    e1 = log.append(
        principal_id="ivan",
        action="a",
        decision="allow",
        scope="s",
        timestamp=base.isoformat(),
    )
    e2 = log.append(
        principal_id="ivan",
        action="b",
        decision="allow",
        scope="s",
        timestamp=(base + timedelta(hours=1)).isoformat(),
    )
    e3 = log.append(
        principal_id="ivan",
        action="c",
        decision="allow",
        scope="s",
        timestamp=(base + timedelta(hours=2)).isoformat(),
    )

    middle_only = log.query(
        since=(base + timedelta(minutes=30)).isoformat(),
        until=(base + timedelta(minutes=90)).isoformat(),
    )
    assert [e.seq for e in middle_only] == [e2.seq]


def test_query_combined_filters(substrate: Substrate) -> None:
    log = AuditLog(substrate)
    log.append(principal_id="ivan", action="a", decision="allow", scope="net")
    log.append(principal_id="other", action="b", decision="deny", scope="net")
    log.append(principal_id="ivan", action="c", decision="allow", scope="fs")

    rows = log.query(principal_id="ivan", scope="net")
    assert [e.action for e in rows] == ["a"]


def test_query_returns_seq_ascending(substrate: Substrate) -> None:
    log = AuditLog(substrate)
    for i in range(5):
        log.append(
            principal_id="ivan",
            action=f"a{i}",
            decision="allow",
            scope="s",
        )
    rows = log.query()
    seqs = [e.seq for e in rows]
    assert seqs == sorted(seqs)


def test_persistent_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    AuditLog(sub1).append(
        principal_id="ivan",
        action="rewrite",
        decision="allow",
        scope="self",
    )
    sub1.close()

    sub2 = Substrate.open(db)
    try:
        rows = AuditLog(sub2).query()
        assert len(rows) == 1
        assert rows[0].action == "rewrite"
        assert rows[0].principal_id == "ivan"
    finally:
        sub2.close()


def test_event_dataclass_is_frozen() -> None:
    e = AuditEvent(
        seq=1,
        timestamp="2026-01-01T00:00:00+00:00",
        principal_id="ivan",
        action="a",
        decision="allow",
        scope="s",
        metadata={},
    )
    with pytest.raises(Exception):
        e.seq = 2  # type: ignore[misc]
