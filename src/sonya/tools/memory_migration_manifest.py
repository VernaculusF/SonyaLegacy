"""Read-only inventory for memory and knowledge migration planning."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MEMORY_TABLES = (
    "episodic_events",
    "semantic_facts",
    "raw_traces",
    "procedural_memory",
    "continuity_events",
    "tool_experiences",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _substrate_manifest(path: Path, *, hash_substrate: bool = False) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        tables: dict[str, Any] = {}
        for table in MEMORY_TABLES:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if exists is None:
                tables[table] = {"exists": False, "rows": 0, "columns": []}
                continue
            columns = [
                row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            ]
            rows = int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            tables[table] = {"exists": True, "rows": rows, "columns": columns}

        version = connection.execute("PRAGMA user_version").fetchone()[0]
        result = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "user_version": int(version),
            "tables": tables,
        }
        fingerprint = json.dumps(
            {"user_version": result["user_version"], "tables": tables},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        result["inventory_sha256"] = hashlib.sha256(fingerprint).hexdigest()
        if hash_substrate:
            result["sha256"] = _sha256(path)
        return result
    finally:
        connection.close()


def _knowledge_manifest(root: Path) -> dict[str, Any]:
    files = []
    if root.exists():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            files.append({
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })
    return {
        "root": str(root.resolve()),
        "files_count": len(files),
        "bytes": sum(item["bytes"] for item in files),
        "files": files,
    }


def _legacy_sources(project_root: Path) -> list[dict[str, str]]:
    candidates = [
        ("knowledge_dir", project_root / "knowledge-base"),
        ("knowledge_dir", project_root / "knowledge_base"),
        ("knowledge_dir", project_root / "data" / "payloads"),
        ("knowledge_dir", project_root / "payloads"),
        ("knowledge_dir", project_root / "kb"),
        ("telegram_desktop_export", project_root / "result.json"),
    ]
    return [
        {"kind": kind, "path": str(path.resolve())}
        for kind, path in candidates
        if path.exists()
    ]


def build_manifest(
    *,
    substrate_path: Path,
    knowledge_root: Path,
    project_root: Path,
    hash_substrate: bool = False,
) -> dict[str, Any]:
    return {
        "format": "sonya-memory-knowledge-manifest-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "substrate": _substrate_manifest(substrate_path, hash_substrate=hash_substrate),
        "knowledge": _knowledge_manifest(knowledge_root),
        "legacy_sources": _legacy_sources(project_root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build read-only Sonya memory migration manifest")
    parser.add_argument("--substrate", type=Path, required=True)
    parser.add_argument("--knowledge-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--hash-substrate",
        action="store_true",
        help="Hash the SQLite file; use only for an offline or backup copy",
    )
    args = parser.parse_args(argv)

    manifest = build_manifest(
        substrate_path=args.substrate,
        knowledge_root=args.knowledge_root,
        project_root=args.project_root,
        hash_substrate=args.hash_substrate,
    )
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
