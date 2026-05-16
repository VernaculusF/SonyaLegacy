from __future__ import annotations

from pathlib import Path


class FilesystemTool:
    """Read/write/list files within allowed paths.

    Sandbox: only operates within project root and configured allowed_paths.
    """

    def __init__(self, allowed_roots: list[Path] | None = None) -> None:
        self._allowed = allowed_roots or [Path(__file__).resolve().parent.parent.parent.parent]

    def _check_path(self, path: str) -> Path:
        p = Path(path).resolve()
        for root in self._allowed:
            if str(p).startswith(str(root.resolve())):
                return p
        raise PermissionError(f"Path {path} is outside allowed roots")

    def read(self, path: str) -> str:
        p = self._check_path(path)
        if not p.exists():
            return f"[ERROR] File not found: {path}"
        return p.read_text(encoding="utf-8", errors="replace")[:10000]

    def write(self, path: str, content: str) -> str:
        p = self._check_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"[OK] Written {len(content)} chars to {path}"

    def list_dir(self, path: str, depth: int = 1) -> str:
        p = self._check_path(path)
        if not p.is_dir():
            return f"[ERROR] Not a directory: {path}"
        lines = []
        for item in sorted(p.iterdir()):
            prefix = "d " if item.is_dir() else "f "
            lines.append(f"{prefix}{item.name}")
        return "\n".join(lines[:100])

    def tree(self, path: str, max_depth: int = 2) -> str:
        p = self._check_path(path)
        lines: list[str] = []
        self._tree_recurse(p, lines, "", max_depth, 0)
        return "\n".join(lines[:200])

    def _tree_recurse(self, p: Path, lines: list[str], prefix: str, max_depth: int, current: int) -> None:
        if current > max_depth:
            return
        for item in sorted(p.iterdir()):
            if item.name.startswith(".") or item.name == "__pycache__" or item.name == "node_modules":
                continue
            lines.append(f"{prefix}{item.name}{'/' if item.is_dir() else ''}")
            if item.is_dir() and current < max_depth:
                self._tree_recurse(item, lines, prefix + "  ", max_depth, current + 1)
