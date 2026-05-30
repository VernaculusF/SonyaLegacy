from __future__ import annotations

import os
from pathlib import Path

# Identity-critical files. Sonya CAN read them but MUST NOT write directly.
# These are the files that define who she is — changes must go through the
# governed-change protocol (selfmod.governed) which requires Ivan's explicit
# approval. Direct filesystem.write to these returns [ERROR].
IDENTITY_CRITICAL_PATHS: tuple[str, ...] = (
    "docs/personality/SOUL.md",
    "docs/personality/APPEARANCE.md",
    "docs/personality/USER.md",
    "docs/personality/SELF.md",
    "docs/personality/LESSONS.md",
    "docs/personality/HEARTBEAT.md",
    "src/sonya/state/seed.py",        # things_not_to_betray seed
    "src/sonya/state/identity.py",    # IdentityWriter — immutable-zone enforcement
    "src/sonya/state/schema.sql",     # substrate schema
    "src/sonya/state/migrations.py",  # substrate migrations
    "src/sonya/selfmod/layers/anchor_integrity.py",  # Layer 4 protection
    "docs/core/SUBSTRATE_STANCE.md",
    "docs/core/SONYA_SYSTEM_CORE.md",
    "docs/core/SONYA_CONSCIOUSNESS_POSITION.md",
    "docs/core/SELF_REWRITE_STANCE.md",
    "docs/core/UNCENSORED_ENVIRONMENT_STANCE.md",
    "docs/core/INTERIM_CRUTCHES.md",
)

# Path components that are NEVER readable or writable. Secrets + git internals.
FORBIDDEN_NAMES: frozenset[str] = frozenset({
    ".env",
    ".env.local",
    "tg.session",
    "tg.session-journal",
    ".git",
})

# Files that contain secrets — NEVER readable, NEVER writable.
FORBIDDEN_SUBPATHS: tuple[str, ...] = (
    ".env",
    ".env.local",
    "tg.session",
    ".git",
)

# Repo top-level dirs Sonya historically dumped knowledge into. Writes here
# are blocked and steered to knowledge.write (facts → ~/.sonya/knowledge/).
_KNOWLEDGE_REPO_DIRS: frozenset[str] = frozenset({
    "knowledge-base",   # dash variant
    "knowledge_base",   # underscore variant
    "data",             # data/payloads/ PayloadsAllTheThings dumps
    "payloads",
    "kb",
})

# File suffixes that, when written to the repo ROOT (no subdir), are almost
# always misplaced knowledge or scratch from a bad fetch.
_KNOWLEDGE_FILE_SUFFIXES: frozenset[str] = frozenset({
    ".md", ".txt", ".csv", ".json", ".html", ".htm",
})

# Legit doc-like files allowed at repo root.
_ALLOWED_ROOT_FILES: frozenset[str] = frozenset({
    "README.md",
    "pyproject.toml",
    ".gitignore",
    ".env.example",
})


class FilesystemTool:
    """Read/write/list files within the project sandbox.

    Sandbox model (revised 2026-05-19):
      * READ — anywhere under project_root EXCEPT FORBIDDEN_SUBPATHS (secrets,
        .git, telegram session). She can study her own code, identity-critical
        files (to know what she is), docs, anything except secrets.
      * WRITE — anywhere under project_root EXCEPT FORBIDDEN_SUBPATHS AND
        EXCEPT IDENTITY_CRITICAL_PATHS. Identity files require governed_change
        protocol (selfmod.governed), not raw filesystem.write.

    Personal AI environment, not a hosted product. Sonya has full read/write
    access to her own code so she can self-modify. The only hard gates are:
      - secrets (would compromise Ivan's accounts)
      - identity (changes there must go through human approval)
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = (
            project_root or Path(__file__).resolve().parent.parent.parent.parent
        ).resolve()

    # --- internal sandbox helpers ---

    def _resolve_under_project(self, path: str) -> Path:
        """Resolve user-provided path against project root and check it stays inside.

        Accepts ``~`` and ``$VAR`` expansions for ergonomics; the resolved
        absolute path must still live under project_root. Anything outside
        (e.g. ``~/.sonya``, ``/etc``) is rejected — Sonya uses code.exec /
        shell.run for those.
        """
        # Strip leading whitespace (model often writes ` /path`).
        path = (path or "").strip()
        if not path:
            raise PermissionError("empty path")
        # Expand ~ / $VAR before resolution. Without this, literal `~` is
        # treated as a relative path under project_root and resolves to
        # `<root>/~` which doesn't exist.
        expanded = os.path.expanduser(os.path.expandvars(path))
        p = Path(expanded)
        if not p.is_absolute():
            p = self._project_root / p
        p = p.resolve()
        try:
            p.relative_to(self._project_root)
        except ValueError as err:
            raise PermissionError(
                f"Path {path} is outside project root ({self._project_root}). "
                f"Use shell.run / code.exec for paths outside the repo "
                f"(e.g. ~/.sonya/, /etc/, /tmp/)."
            ) from err
        return p

    def _check_forbidden(self, p: Path) -> None:
        """Hard deny — applies to BOTH read and write."""
        # Component-level check (catches `.env`, `.git/...`, etc anywhere)
        for part in p.parts:
            if part in FORBIDDEN_NAMES:
                raise PermissionError(f"Forbidden path component: {part}")
        # Subpath-level check
        try:
            rel = p.relative_to(self._project_root).as_posix()
        except ValueError:
            return
        for forbidden in FORBIDDEN_SUBPATHS:
            if rel == forbidden or rel.startswith(forbidden + "/"):
                raise PermissionError(f"Forbidden path: {rel}")

    def _check_writable(self, p: Path) -> None:
        """Write deny-list: identity-critical files require governed change."""
        try:
            rel = p.relative_to(self._project_root).as_posix()
        except ValueError as err:
            raise PermissionError(f"Path outside project: {p}") from err
        for protected in IDENTITY_CRITICAL_PATHS:
            if rel == protected:
                raise PermissionError(
                    f"Identity-critical file: {rel}. "
                    f"Use selfmod.governed to propose changes — Ivan's explicit "
                    f"approval is required for personality / identity files."
                )
        # Knowledge belongs in ~/.sonya/knowledge/ via the knowledge.* tools,
        # NOT in repo dirs. Block re-creation of the legacy mess that Sonya
        # used to scatter facts into. Historically she wrote into:
        #   - knowledge-base/  (dash)
        #   - knowledge_base/  (underscore)
        #   - data/payloads/   (PayloadsAllTheThings dumps)
        #   - repo root         (e.g. stray 2022-07-30.csv from a bad fetch)
        # Steer all of it to knowledge.write so facts live in
        # ~/.sonya/knowledge/ (substrate-side, survives deploys, not in git).
        first_seg = rel.split("/", 1)[0]
        if first_seg in _KNOWLEDGE_REPO_DIRS:
            raise PermissionError(
                f"Don't write knowledge into repo ({rel}). Use the "
                f"knowledge.write tool — facts live in ~/.sonya/knowledge/, "
                f"persistent across deploys, not in git. "
                f"Example: [TOOL: knowledge.write pentest/sqli]\\n<content>"
            )
        # Loose doc-like files dumped at repo root (no subdir) are almost
        # always misplaced knowledge / scratch from a fetch. Repo root is for
        # project files, not her notes. Block .md/.txt/.csv/.json at root.
        if "/" not in rel and p.suffix.lower() in _KNOWLEDGE_FILE_SUFFIXES:
            # Allow the handful of legit root files (README etc.).
            if rel not in _ALLOWED_ROOT_FILES:
                raise PermissionError(
                    f"Don't dump notes/data at repo root ({rel}). If it's a "
                    f"fact or reference, use knowledge.write (lives in "
                    f"~/.sonya/knowledge/). If it's scratch, use code.exec / "
                    f"a temp path under your home, not the repo."
                )

    # --- public API ---

    def read(self, path: str) -> str:
        try:
            p = self._resolve_under_project(path)
            self._check_forbidden(p)
        except PermissionError as err:
            return f"[ERROR] {err}"
        if not p.exists():
            return f"[ERROR] File not found: {path}"
        if not p.is_file():
            return f"[ERROR] Not a file: {path}"
        return p.read_text(encoding="utf-8", errors="replace")[:10000]

    def write(self, path: str, content: str) -> str:
        # Defense in depth: reject paths with newline / control / quote chars.
        # Even if upstream parser fails, we don't want to create a literal
        # `workspace/foo.md\n#` file. Forward slashes and dots are fine —
        # those are normal path components.
        if not path or not path.strip():
            return "[ERROR] filesystem.write: empty path"
        # Check for control chars BEFORE strip — strip would silently remove
        # trailing \r etc.
        if any(ch in path for ch in ("\n", "\r", "\0", '"')):
            return (
                "[ERROR] filesystem.write: path contains newline/control/quote chars. "
                "Use block form: first line = path, remaining lines = content."
            )
        path = path.strip()
        try:
            p = self._resolve_under_project(path)
            self._check_forbidden(p)
            self._check_writable(p)
        except PermissionError as err:
            return f"[ERROR] {err}"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"[OK] Written {len(content)} chars to {path}"

    def list_dir(self, path: str, depth: int = 1) -> str:
        try:
            p = self._resolve_under_project(path)
            self._check_forbidden(p)
        except PermissionError as err:
            return f"[ERROR] {err}"
        if not p.is_dir():
            return f"[ERROR] Not a directory: {path}"
        lines = []
        for item in sorted(p.iterdir()):
            # Hide forbidden items from listing
            if item.name in FORBIDDEN_NAMES:
                continue
            prefix = "d " if item.is_dir() else "f "
            lines.append(f"{prefix}{item.name}")
        return "\n".join(lines[:100])

    def tree(self, path: str, max_depth: int = 2) -> str:
        try:
            p = self._resolve_under_project(path)
            self._check_forbidden(p)
        except PermissionError as err:
            return f"[ERROR] {err}"
        lines: list[str] = []
        self._tree_recurse(p, lines, "", max_depth, 0)
        return "\n".join(lines[:200])

    def _tree_recurse(self, p: Path, lines: list[str], prefix: str, max_depth: int, current: int) -> None:
        if current > max_depth:
            return
        if not p.is_dir():
            return
        for item in sorted(p.iterdir()):
            if item.name.startswith(".") or item.name == "__pycache__" or item.name == "node_modules":
                continue
            if item.name in FORBIDDEN_NAMES:
                continue
            lines.append(f"{prefix}{item.name}{'/' if item.is_dir() else ''}")
            if item.is_dir() and current < max_depth:
                self._tree_recurse(item, lines, prefix + "  ", max_depth, current + 1)
