"""Plan or apply exact semantic-fact deduplication on a backup copy."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


_GROUP_COLUMNS = ("fact_type", "statement", "scope", "project_id", "retention_policy")


def _connect(path: Path, *, read_only: bool) -> sqlite3.Connection:
    if read_only:
        return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    return sqlite3.connect(path)


def _duplicate_groups(connection: sqlite3.Connection) -> list[tuple[Any, ...]]:
    columns = ", ".join(_GROUP_COLUMNS)
    return connection.execute(
        f"SELECT {columns} FROM semantic_facts "
        "WHERE statement IS NOT NULL AND statement != '' "
        f"GROUP BY {columns} HAVING count(*) > 1"
    ).fetchall()


def plan_semantic_dedup(path: Path) -> dict[str, int]:
    connection = _connect(path, read_only=True)
    try:
        groups = _duplicate_groups(connection)
        extra_rows = 0
        for group in groups:
            where = " AND ".join(f"{column} IS ?" for column in _GROUP_COLUMNS)
            count = connection.execute(
                f"SELECT count(*) FROM semantic_facts WHERE {where}",
                group,
            ).fetchone()[0]
            extra_rows += int(count) - 1
        return {"groups": len(groups), "extra_rows": extra_rows}
    finally:
        connection.close()


def _json_union(values: list[str]) -> str:
    merged: set[str] = set()
    for value in values:
        try:
            parsed = json.loads(value or "[]")
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            merged.update(str(item) for item in parsed)
    return json.dumps(sorted(merged), ensure_ascii=False)


def apply_semantic_dedup(path: Path, *, target_is_backup_copy: bool) -> dict[str, int]:
    if not target_is_backup_copy:
        raise PermissionError("semantic dedup apply requires explicit backup copy confirmation")

    connection = _connect(path, read_only=False)
    try:
        groups = _duplicate_groups(connection)
        deleted_rows = 0
        where = " AND ".join(f"{column} IS ?" for column in _GROUP_COLUMNS)
        for group in groups:
            rows = connection.execute(
                "SELECT fact_id, confidence, last_reinforced_at, "
                f"source_event_ids_json, contradiction_flags_json FROM semantic_facts WHERE {where}",
                group,
            ).fetchall()
            keeper = max(rows, key=lambda row: (float(row[1] or 0), str(row[2] or ""), str(row[0])))
            source_ids = _json_union([str(row[3] or "[]") for row in rows])
            contradiction_flags = _json_union([str(row[4] or "[]") for row in rows])
            connection.execute(
                "UPDATE semantic_facts SET confidence = ?, last_reinforced_at = ?, "
                "source_event_ids_json = ?, contradiction_flags_json = ? WHERE fact_id = ?",
                (keeper[1], keeper[2], source_ids, contradiction_flags, keeper[0]),
            )
            delete_ids = [row[0] for row in rows if row[0] != keeper[0]]
            connection.executemany(
                "DELETE FROM semantic_facts WHERE fact_id = ?",
                [(fact_id,) for fact_id in delete_ids],
            )
            deleted_rows += len(delete_ids)
        connection.commit()
        return {"groups": len(groups), "deleted_rows": deleted_rows}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan/apply exact semantic dedup on a backup copy")
    parser.add_argument("substrate", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--target-is-backup-copy", action="store_true")
    args = parser.parse_args(argv)

    result = (
        apply_semantic_dedup(args.substrate, target_is_backup_copy=args.target_is_backup_copy)
        if args.apply
        else plan_semantic_dedup(args.substrate)
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
