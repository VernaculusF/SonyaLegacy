"""KnowledgeTool — её persistent knowledge base в ~/.sonya/knowledge/.

Архитектура:
- Skills (Python-код в src/sonya/skills/builtins/) = поведение, runtime executors
- Knowledge (markdown в ~/.sonya/knowledge/) = факты, перечитывается при каждом обращении

Раньше Соня дублировала knowledge в две папки в repo (`knowledge-base/wp/`,
`knowledge_base/pentest/`) и третьим способом — как Python-константы в
.py файлах. Этот модуль централизует knowledge в одно место в substrate-side
storage и предоставляет tool family `knowledge.*` для работы с ним.

Структура:
    ~/.sonya/knowledge/
      pentest/
        sqli.md
        xss.md
        osint.md
      wp/
        wpscan.md
        karrab.md
      _index.json   (auto-generated table of contents — topic → files)

Tool calls:
- `knowledge.list [topic?]` — список тем или файлов в теме
- `knowledge.read <topic/file>` — содержимое файла
- `knowledge.write <topic/file>\n<content>` — создать/обновить
- `knowledge.search <query>` — full-text grep по всем .md
- `knowledge.delete <topic/file>` — удалить
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


# Reserved subpaths — things she shouldn't write into knowledge (these
# would silently shadow real configuration / break things).
_FORBIDDEN_NAMES = frozenset({
    "_index.json",
    ".git",
    ".env",
    "config.json",
})


def _slugify(name: str) -> str:
    """Path-safe slug. Latin/cyrillic letters + digits + dash/underscore."""
    name = name.strip().lower()
    # Replace spaces with dash
    name = re.sub(r"\s+", "-", name)
    # Drop everything except letters/digits/dash/underscore/slash/dot
    name = re.sub(r"[^a-z0-9а-яё/_\-.]+", "", name)
    # Collapse multiple slashes
    name = re.sub(r"/+", "/", name)
    return name.strip("/")


class KnowledgeTool:
    """Knowledge base I/O bound to a single root directory.

    Default root is ``~/.sonya/knowledge/``. Substrate-side, not in repo —
    survives across deploys, doesn't pollute git.
    """

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            home = Path.home()
            root = home / ".sonya" / "knowledge"
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    # ---------- private path helpers ----------

    def _resolve(self, rel_path: str) -> Path:
        """Resolve a relative path under root, refusing escapes / forbidden names."""
        slug = _slugify(rel_path)
        if not slug:
            raise ValueError("path required")
        # Append .md if no extension
        if "." not in slug.rsplit("/", 1)[-1]:
            slug += ".md"
        # Forbidden names
        leaf = slug.rsplit("/", 1)[-1]
        if leaf in _FORBIDDEN_NAMES:
            raise PermissionError(f"forbidden filename: {leaf}")
        target = (self._root / slug).resolve()
        # Refuse to escape root
        try:
            target.relative_to(self._root)
        except ValueError as err:
            raise PermissionError(f"path escape: {rel_path}") from err
        return target

    # ---------- public tool surface ----------

    def list(self, arg: str = "") -> str:
        """List topics (top-level dirs) or files within a topic."""
        topic = (arg or "").strip()
        if not topic:
            # Top-level: list topic dirs
            topics = sorted(
                p.name for p in self._root.iterdir() if p.is_dir() and not p.name.startswith(".")
            )
            if not topics:
                return "(knowledge base empty)"
            return "topics:\n" + "\n".join(f"  {t}" for t in topics)
        # Inside a topic: list .md files
        try:
            slug = _slugify(topic)
            topic_dir = (self._root / slug).resolve()
            topic_dir.relative_to(self._root)
        except (ValueError, PermissionError):
            return f"[ERROR] invalid topic: {topic}"
        if not topic_dir.exists() or not topic_dir.is_dir():
            return f"(no such topic: {topic})"
        files = sorted(p.name for p in topic_dir.iterdir() if p.is_file())
        if not files:
            return f"(topic {topic} has no files)"
        return f"{topic}/:\n" + "\n".join(f"  {f}" for f in files)

    def read(self, arg: str) -> str:
        """Read a knowledge file by relative path (e.g. 'pentest/sqli')."""
        path = (arg or "").strip()
        if not path:
            return "[ERROR] knowledge.read needs path"
        try:
            target = self._resolve(path)
        except (ValueError, PermissionError) as err:
            return f"[ERROR] {err}"
        if not target.exists():
            return f"[ERROR] not found: {path}"
        if not target.is_file():
            return f"[ERROR] not a file: {path}"
        try:
            return target.read_text(encoding="utf-8")
        except Exception as err:
            return f"[ERROR] read failed: {err}"

    def write(self, arg: str) -> str:
        """Write/append knowledge.

        Format: first line = relative path, rest = content.
        Path can be inside backticks for clarity.

        ```
        knowledge.write pentest/sqli
        # SQL Injection notes

        ## Entry points
        ...
        ```

        Behavior: full-replace by default. Existing content gets a one-line
        archive marker prepended in the previous version.
        """
        if not arg or not arg.strip():
            return "[ERROR] knowledge.write needs <path>\\n<content>"
        # Split first line as path, rest as content
        first_nl = arg.find("\n")
        if first_nl < 0:
            return "[ERROR] knowledge.write: missing content after path"
        path_line = arg[:first_nl].strip()
        content = arg[first_nl + 1:]
        if not path_line:
            return "[ERROR] knowledge.write: empty path"
        if not content.strip():
            return "[ERROR] knowledge.write: empty content"
        try:
            target = self._resolve(path_line)
        except (ValueError, PermissionError) as err:
            return f"[ERROR] {err}"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Add a header marker if file is new
        is_new = not target.exists()
        if is_new:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            content = f"<!-- created {stamp} -->\n{content}"
        target.write_text(content, encoding="utf-8")
        size = target.stat().st_size
        return f"[OK] knowledge.write {target.relative_to(self._root).as_posix()} ({size} bytes, {'new' if is_new else 'updated'})"

    def search(self, arg: str) -> str:
        """Full-text search across all knowledge files. Returns matches with context."""
        query = (arg or "").strip()
        if not query:
            return "[ERROR] knowledge.search needs query"
        if len(query) < 3:
            return "[ERROR] knowledge.search: query too short (min 3 chars)"
        q_lower = query.lower()
        hits: list[tuple[str, int, str]] = []
        for md_file in self._root.rglob("*.md"):
            try:
                rel = md_file.relative_to(self._root).as_posix()
                lines = md_file.read_text(encoding="utf-8", errors="replace").splitlines()
                for i, line in enumerate(lines, 1):
                    if q_lower in line.lower():
                        hits.append((rel, i, line.strip()[:200]))
                        if len(hits) >= 30:
                            break
            except Exception:
                continue
            if len(hits) >= 30:
                break
        if not hits:
            return f"(no matches for {query!r})"
        result = [f"matches for {query!r}:"]
        for rel, lineno, snippet in hits:
            result.append(f"  {rel}:{lineno}: {snippet}")
        if len(hits) >= 30:
            result.append("  (showing first 30)")
        return "\n".join(result)

    def delete(self, arg: str) -> str:
        """Delete a knowledge file."""
        path = (arg or "").strip()
        if not path:
            return "[ERROR] knowledge.delete needs path"
        try:
            target = self._resolve(path)
        except (ValueError, PermissionError) as err:
            return f"[ERROR] {err}"
        if not target.exists():
            return f"[ERROR] not found: {path}"
        if not target.is_file():
            return f"[ERROR] not a file: {path}"
        target.unlink()
        return f"[OK] knowledge.delete {target.relative_to(self._root).as_posix()}"


def migrate_legacy_knowledge_dirs(project_root: Path, knowledge_root: Path | None = None) -> int:
    """One-shot migration: move ``knowledge-base/`` and ``knowledge_base/``
    из repo в ~/.sonya/knowledge/ если они там лежат.

    Также мигрирует knowledge-как-Python-константы (OSINT_KB / SQLI_KB /
    WP_KB) из старых builtin skill-модулей если они ещё есть.

    Idempotent: если уже мигрировано — no-op.

    Returns: количество перенесённых файлов.
    """
    if knowledge_root is None:
        knowledge_root = Path.home() / ".sonya" / "knowledge"
    knowledge_root.mkdir(parents=True, exist_ok=True)
    migrated = 0

    # Part 1: legacy markdown dirs (knowledge-base/, knowledge_base/, data/payloads/, kb/)
    legacy_dirs = [
        project_root / "knowledge-base",
        project_root / "knowledge_base",
        project_root / "data" / "payloads",
        project_root / "payloads",
        project_root / "kb",
    ]
    for legacy in legacy_dirs:
        if not legacy.exists() or not legacy.is_dir():
            continue
        # Namespace the destination by the legacy dir name so files from
        # different sources don't collide (e.g. data/payloads/sqli.md vs
        # an extracted pentest/sqli.md). payloads → pentest/ (her usage).
        if legacy.name == "payloads":
            dest_prefix = knowledge_root / "pentest"
        else:
            dest_prefix = knowledge_root
        for md_file in legacy.rglob("*.md"):
            rel = md_file.relative_to(legacy)
            target = dest_prefix / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(md_file.read_bytes())
                migrated += 1

    # Part 2: knowledge-as-Python-constants in builtin skill modules.
    # Соня создала osint.py / sqli.py / wp_pentest.py где KB лежал как
    # `OSINT_KB = r"""..."""`. Извлекаем эти константы и пишем как .md.
    builtins_dir = project_root / "src" / "sonya" / "skills" / "builtins"
    fake_skills_to_kb = {
        "osint.py": ("pentest/osint.md", "OSINT_KB"),
        "sqli.py": ("pentest/sqli.md", "SQLI_KB"),
        "wp_pentest.py": ("pentest/wordpress.md", "WP_KB"),
    }
    for fname, (target_rel, var_name) in fake_skills_to_kb.items():
        src_file = builtins_dir / fname
        if not src_file.exists():
            continue
        target = knowledge_root / target_rel
        if target.exists():
            continue  # already migrated
        try:
            content = src_file.read_text(encoding="utf-8")
        except Exception:
            continue
        # Find the KB constant: `OSINT_KB = r"""..."""`
        import re as _re
        match = _re.search(
            rf'{var_name}\s*=\s*r?"""(.*?)"""',
            content,
            _re.DOTALL,
        )
        if not match:
            continue
        kb_text = match.group(1).strip()
        target.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        header = (
            f"<!-- migrated from src/sonya/skills/builtins/{fname} on {stamp} -->\n"
            "<!-- previously stored as Python const, now first-class knowledge -->\n\n"
        )
        target.write_text(header + kb_text + "\n", encoding="utf-8")
        migrated += 1

    return migrated
