from __future__ import annotations

import json

import pytest

from sonya.state.substrate import Substrate
from sonya.tools.memory_semantic_dedup import apply_semantic_dedup, plan_semantic_dedup


def test_semantic_dedup_plan_and_apply_merge_provenance(tmp_path) -> None:
    db_path = tmp_path / "backup-copy.db"
    sub = Substrate.open(db_path)
    try:
        rows = [
            ("fact-a", 0.6, '["event-a"]', '["old"]', "2026-01-01"),
            ("fact-b", 0.9, '["event-b"]', '["new"]', "2026-02-01"),
        ]
        for fact_id, confidence, sources, flags, reinforced in rows:
            sub.connection.execute(
                "INSERT INTO semantic_facts "
                "(fact_id, fact_type, statement, source_event_ids_json, confidence, "
                "last_reinforced_at, contradiction_flags_json, scope, project_id, retention_policy) "
                "VALUES (?, 'preference', 'same private statement', ?, ?, ?, ?, 'global', '', 'long')",
                (fact_id, sources, confidence, reinforced, flags),
            )
        sub.connection.commit()
    finally:
        sub.close()

    plan = plan_semantic_dedup(db_path)

    assert plan == {"groups": 1, "extra_rows": 1}
    result = apply_semantic_dedup(db_path, target_is_backup_copy=True)
    assert result == {"groups": 1, "deleted_rows": 1}

    sub = Substrate.open(db_path)
    try:
        row = sub.connection.execute(
            "SELECT fact_id, confidence, source_event_ids_json, contradiction_flags_json "
            "FROM semantic_facts"
        ).fetchone()
    finally:
        sub.close()
    assert row[0] == "fact-b"
    assert row[1] == 0.9
    assert json.loads(row[2]) == ["event-a", "event-b"]
    assert json.loads(row[3]) == ["new", "old"]


def test_semantic_dedup_refuses_apply_without_backup_confirmation(tmp_path) -> None:
    db_path = tmp_path / "live.db"
    sub = Substrate.open(db_path)
    sub.close()

    with pytest.raises(PermissionError, match="backup copy"):
        apply_semantic_dedup(db_path, target_is_backup_copy=False)
