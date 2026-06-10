from __future__ import annotations

import json
import hashlib

from sonya.state.substrate import Substrate
from sonya.tools.memory_migration_manifest import build_manifest, main


def test_manifest_reports_counts_schema_hashes_and_sources_without_content(tmp_path) -> None:
    db_path = tmp_path / "sonya.db"
    sub = Substrate.open(db_path)
    try:
        sub.connection.execute(
            "INSERT INTO semantic_facts "
            "(fact_id, fact_type, statement, source_event_ids_json, confidence, "
            "last_reinforced_at, contradiction_flags_json) "
            "VALUES ('fact-1', 'private', 'do not leak this statement', '[]', 1.0, '', '[]')"
        )
        sub.connection.commit()
    finally:
        sub.close()

    knowledge_root = tmp_path / "knowledge"
    knowledge_root.mkdir()
    (knowledge_root / "private.md").write_text("do not leak this knowledge", encoding="utf-8")
    project_root = tmp_path / "project"
    (project_root / "knowledge-base").mkdir(parents=True)
    (project_root / "knowledge-base" / "legacy.md").write_text("legacy", encoding="utf-8")
    (project_root / "result.json").write_text("{}", encoding="utf-8")

    manifest = build_manifest(
        substrate_path=db_path,
        knowledge_root=knowledge_root,
        project_root=project_root,
    )
    rendered = json.dumps(manifest, sort_keys=True)

    assert manifest["read_only"] is True
    assert manifest["substrate"]["tables"]["semantic_facts"]["rows"] == 1
    assert "statement" in manifest["substrate"]["tables"]["semantic_facts"]["columns"]
    assert manifest["knowledge"]["files"][0]["path"] == "private.md"
    assert len(manifest["knowledge"]["files"][0]["sha256"]) == 64
    assert {item["kind"] for item in manifest["legacy_sources"]} == {
        "knowledge_dir",
        "telegram_desktop_export",
    }
    assert "do not leak this statement" not in rendered
    assert "do not leak this knowledge" not in rendered


def test_manifest_cli_writes_json_without_modifying_substrate(tmp_path, capsys) -> None:
    db_path = tmp_path / "sonya.db"
    sub = Substrate.open(db_path)
    sub.close()
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()

    knowledge_root = tmp_path / "knowledge"
    knowledge_root.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()

    assert main([
        "--substrate", str(db_path),
        "--knowledge-root", str(knowledge_root),
        "--project-root", str(project_root),
    ]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before
    assert payload["read_only"] is True
