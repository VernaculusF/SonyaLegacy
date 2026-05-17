from __future__ import annotations

from pathlib import Path

# Subpaths (relative to project root) where Sonya is allowed to WRITE.
# Read access is wider — see READ_ALLOWED_ROOTS below.
WRITE_ALLOWED_SUBPATHS: tuple[str, ...] = (
    "src/sonya/tools/plugins",
    "workspace",
)

# Path components that are NEVER readable or writable, even by accident.
FORBIDDEN_NAMES: frozenset[str] = frozenset({
    ".env",
    ".env.local",
    "tg.session",
    "tg.session-journal",
    ".git",
})

# Forbidden subpaths (project-relative) that contain secrets or system invariants.
FORBIDDEN_SUBPATHS: tuple[str, ...] = (
    "src/sonya/state/schema.sql",
    "src/sonya/state/seed.py",
    "docs/personality/SOUL.md",
    ".env",
    ".env.local",
    "tg.session",
    ".git",
)


class FilesystemTool:
    """Read/write/list files within allowed paths.

    Sandbox model:
      * READ allowed anywhere under project_root (so Sonya can study her code, docs, etc.)
        EXCEPT FORBIDDEN_SUBPATHS (secrets, anchors, schema).
      * WRITE only inside WRITE_ALLOWED_SUBPATHS (`workspace/` and `src/sonya/tools/plugins/`).
        WRITE to FORBIDDEN_SUBPATHS is rejected even when the parent allowlist matches.

    See KNOWN_ISSUES S-12 and SUBSTRATE_STANCE §9 — self-modification of identity-critical
    files must go through the self-modification pipeline, not raw filesystem writes.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = (
            project_root or Path(__file__).resolve().parent.parent.parent.parent
        ).resolve()

    # --- internal sandbox helpers ---

    def _resolve_under_project(self, path: str) -> Path:
        """Resolve user-provided path against project root and check it stays inside."""
        p = (self._project_root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        try:
            p.relative_to(self._project_root)
        except ValueError as err:
            raise PermissionError(f"Path {path} is outside project root") from err
        return p

    def _check_forbidden(self, p: Path) -> None:
        # Component-level check (catches `.env`, `.git/...`, etc anywhere)
        for part in p.parts:
            if part in FORBIDDEN_NAMES:
                raise PermissionError(f"Forbidden path component: {part}")
        # Subpath-level check (catches anchored files like docs/personality/SOUL.md)
        try:
            rel = p.relative_to(self._project_root).as_posix()
        except ValueError:
            return
        for forbidden in FORBIDDEN_SUBPATHS:
            if rel == forbidden or rel.startswith(forbidden + "/"):
                raise PermissionError(f"Forbidden path: {rel}")

    def _check_writable(self, p: Path) -> None:
        """Ensure path is inside one of WRITE_ALLOWED_SUBPATHS."""
        try:
            rel = p.relative_to(self._project_root).as_posix()
        except ValueError as err:
            raise PermissionError(f"Path outside project: {p}") from err
        for allowed in WRITE_ALLOWED_SUBPATHS:
            if rel == allowed or rel.startswith(allowed + "/"):
                return
        raise PermissionError(
            f"Write not allowed: {rel}. Writes are only permitted under: "
            + ", ".join(WRITE_ALLOWED_SUBPATHS)
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
