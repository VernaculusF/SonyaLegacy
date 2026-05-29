"""KnowledgeTool — persistent markdown KB в ~/.sonya/knowledge/.

Tests: write/read/list/search/delete, path-safety, legacy migration.
"""
from __future__ import annotations

from pathlib import Path

from sonya.tools.knowledge import KnowledgeTool, migrate_legacy_knowledge_dirs


def _kt(tmp_path: Path) -> KnowledgeTool:
    return KnowledgeTool(root=tmp_path / "knowledge")


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    res = kt.write("pentest/sqli\n# SQL Injection\n\n## Entry points\n' OR '1'='1")
    assert "[OK]" in res
    assert "pentest/sqli.md" in res
    content = kt.read("pentest/sqli")
    assert "SQL Injection" in content
    assert "Entry points" in content


def test_write_appends_md_extension(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    kt.write("notes/quick\nhello")
    # readable both with and without .md
    assert "hello" in kt.read("notes/quick")
    assert "hello" in kt.read("notes/quick.md")


def test_write_new_adds_created_marker(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    kt.write("topic/file\ncontent")
    content = kt.read("topic/file")
    assert "<!-- created" in content


def test_list_topics_and_files(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    assert "empty" in kt.list().lower()
    kt.write("pentest/sqli\nx")
    kt.write("pentest/xss\ny")
    kt.write("wp/wpscan\nz")
    topics = kt.list()
    assert "pentest" in topics
    assert "wp" in topics
    files = kt.list("pentest")
    assert "sqli.md" in files
    assert "xss.md" in files


def test_search_finds_matches(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    kt.write("pentest/sqli\n# SQLi\nUNION SELECT bypass technique")
    kt.write("pentest/xss\n# XSS\nUnicode bypass payload")
    res = kt.search("bypass")
    assert "sqli.md" in res
    assert "xss.md" in res
    res2 = kt.search("UNION")
    assert "sqli.md" in res2
    assert "xss.md" not in res2


def test_search_too_short(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    assert "too short" in kt.search("ab")


def test_delete(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    kt.write("topic/doomed\ncontent")
    assert "content" in kt.read("topic/doomed")
    res = kt.delete("topic/doomed")
    assert "[OK]" in res
    assert "not found" in kt.read("topic/doomed")


def test_path_escape_blocked(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    # Try to escape root
    res = kt.write("../../etc/passwd\nhacked")
    # _slugify strips the ../ → becomes 'etc/passwd' under root; either way
    # it must NOT write outside root.
    outside = tmp_path / "etc" / "passwd"
    assert not outside.exists()


def test_forbidden_filename_blocked(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    res = kt.write("_index.json\n{}")
    assert "[ERROR]" in res or "forbidden" in res.lower()


def test_read_missing(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    assert "not found" in kt.read("does/not/exist")


def test_write_empty_content_rejected(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    assert "[ERROR]" in kt.write("topic/file\n   ")


def test_write_no_content_rejected(tmp_path: Path) -> None:
    kt = _kt(tmp_path)
    assert "[ERROR]" in kt.write("just-a-path-no-newline")


# ---------- legacy migration ----------


def test_migrate_legacy_dirs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "knowledge-base" / "wp").mkdir(parents=True)
    (project / "knowledge-base" / "wp" / "wpscan.md").write_text("# wpscan notes", encoding="utf-8")
    (project / "knowledge_base" / "pentest").mkdir(parents=True)
    (project / "knowledge_base" / "pentest" / "method.md").write_text("# methodology", encoding="utf-8")

    kroot = tmp_path / "knowledge"
    migrated = migrate_legacy_knowledge_dirs(project, knowledge_root=kroot)
    assert migrated == 2
    assert (kroot / "wp" / "wpscan.md").exists()
    assert (kroot / "pentest" / "method.md").exists()
    assert "wpscan notes" in (kroot / "wp" / "wpscan.md").read_text(encoding="utf-8")


def test_migrate_legacy_dirs_idempotent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "knowledge-base").mkdir(parents=True)
    (project / "knowledge-base" / "x.md").write_text("data", encoding="utf-8")
    kroot = tmp_path / "knowledge"
    first = migrate_legacy_knowledge_dirs(project, knowledge_root=kroot)
    assert first == 1
    second = migrate_legacy_knowledge_dirs(project, knowledge_root=kroot)
    assert second == 0  # already migrated


def test_migrate_python_const_kb(tmp_path: Path) -> None:
    """KB stored as Python const (OSINT_KB = r'''...''') gets extracted to .md."""
    project = tmp_path / "project"
    builtins = project / "src" / "sonya" / "skills" / "builtins"
    builtins.mkdir(parents=True)
    (builtins / "osint.py").write_text(
        'SKILL_ID = "skill-osint"\n\nOSINT_KB = r"""\n# OSINT KB\n\n## Google Dorks\nsite:target.com\n"""\n\ndef run(ctx): pass\n',
        encoding="utf-8",
    )
    kroot = tmp_path / "knowledge"
    migrated = migrate_legacy_knowledge_dirs(project, knowledge_root=kroot)
    assert migrated == 1
    osint_md = kroot / "pentest" / "osint.md"
    assert osint_md.exists()
    content = osint_md.read_text(encoding="utf-8")
    assert "OSINT KB" in content
    assert "Google Dorks" in content
    assert "migrated from" in content


def test_migrate_data_payloads_dir(tmp_path: Path) -> None:
    """data/payloads/*.md (PayloadsAllTheThings dumps) → knowledge/pentest/."""
    project = tmp_path / "project"
    (project / "data" / "payloads").mkdir(parents=True)
    (project / "data" / "payloads" / "sqli.md").write_text(
        "# SQL Injection\nUNION SELECT", encoding="utf-8"
    )
    kroot = tmp_path / "knowledge"
    migrated = migrate_legacy_knowledge_dirs(project, knowledge_root=kroot)
    assert migrated == 1
    assert (kroot / "pentest" / "sqli.md").exists()
    assert "UNION SELECT" in (kroot / "pentest" / "sqli.md").read_text(encoding="utf-8")


def test_migrate_payloads_dir_namespaced_to_pentest(tmp_path: Path) -> None:
    """A top-level payloads/ dir lands under pentest/ to match her usage."""
    project = tmp_path / "project"
    (project / "payloads").mkdir(parents=True)
    (project / "payloads" / "xss.md").write_text("# XSS", encoding="utf-8")
    kroot = tmp_path / "knowledge"
    migrated = migrate_legacy_knowledge_dirs(project, knowledge_root=kroot)
    assert migrated == 1
    assert (kroot / "pentest" / "xss.md").exists()
