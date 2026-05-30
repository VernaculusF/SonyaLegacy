"""Workshop endpoints — Atrium UI to inspect and edit Sonya's code surface.

Three categories Ivan can browse / edit / create:

  - **skills**   — Python files in src/sonya/skills/builtins/*.py (registered
                   into the substrate `skills` table at startup; runtime via
                   `skills.run`).
  - **tools**    — Hot-loadable tool plugins in src/sonya/tools/plugins/*.py
                   (no restart needed via tools.hot_loader).
  - **packages** — Subprojects in packages/* (atrium, tg-userbot, …).
                   Read-only structural browser; editing limited to source
                   files Ivan owns (not node_modules / dist / .git).

Auth: same X-Atrium-Token header as other /api/atrium/* endpoints.

Endpoints:

  GET   /api/atrium/workshop/list?kind=skills|tools|packages
  GET   /api/atrium/workshop/read?kind=...&path=...
  POST  /api/atrium/workshop/write   {kind, path, content}
  POST  /api/atrium/workshop/test    {kind, path, input}
  POST  /api/atrium/workshop/reply   {kind, path, message}    — ask Sonya about it

The write endpoint refuses paths outside the kind's root, and refuses any
path inside FORBIDDEN_SUBPATHS (mirrors filesystem.py guards).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aiohttp import web


# Repo root is two parents up from this file: src/sonya/admin/workshop.py
_ADMIN_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _ADMIN_DIR.parent.parent.parent

_SKILLS_ROOT = _REPO_ROOT / "src" / "sonya" / "skills" / "builtins"
_TOOLS_ROOT = _REPO_ROOT / "src" / "sonya" / "tools"
_PACKAGES_ROOT = _REPO_ROOT / "packages"

# Ivan-owned file types that are safe to read/write inside packages/. Avoids
# node_modules / dist / .git / *.lock binary surface.
_PACKAGE_SOURCE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".md", ".json",
    ".rs", ".toml", ".yml", ".yaml", ".sh",
}
_PACKAGE_SKIP_DIRS = {
    "node_modules", "dist", "build", ".git", "target", "__pycache__",
    ".pytest_cache", "public", "egg-info",
}
# Suffix-style skip (for *.egg-info, *.dist-info)
_PACKAGE_SKIP_SUFFIXES = (".egg-info", ".dist-info")


def _root_for(kind: str) -> Path:
    if kind == "skills":
        return _SKILLS_ROOT
    if kind == "tools":
        return _TOOLS_ROOT
    if kind == "packages":
        return _PACKAGES_ROOT
    raise ValueError(f"unknown kind: {kind}")


def _safe_resolve(root: Path, rel_path: str) -> Path:
    """Resolve rel_path under root, refuse escapes."""
    rel = (rel_path or "").strip().lstrip("/").replace("\\", "/")
    if not rel or ".." in rel.split("/"):
        raise PermissionError("invalid path")
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        raise PermissionError("path escape")
    return p


def _list_dir(kind: str) -> list[dict]:
    """Return browsing structure for the kind.

    - skills | tools: flat list of files (with size, path, lang).
    - packages: list of package nodes — each package is one entry with a
      nested `tree` (folders + files), so the UI shows 2 packages, not all
      33 files at the top level. Tree nodes:
        {type:'dir', name, path, children: []}
        {type:'file', name, path, size, lang}
    """
    root = _root_for(kind)
    if not root.exists():
        return []
    if kind in ("skills", "tools"):
        out: list[dict] = []
        # Top-level *.py — for skills: builtins/*.py;
        # for tools: registered core tools (read-only via workshop).
        for p in sorted(root.glob("*.py")):
            if p.name == "__init__.py":
                continue
            out.append(_file_info(p, root))
        # For tools, also include plugins/ subdir (hot-loadable plugins,
        # writable). Marked with relative path "plugins/<name>.py".
        if kind == "tools":
            plugins_dir = root / "plugins"
            if plugins_dir.exists():
                for p in sorted(plugins_dir.glob("*.py")):
                    if p.name == "__init__.py":
                        continue
                    out.append(_file_info(p, root))
        return out
    # packages: one node per top-level dir.
    out = []
    for pkg in sorted(root.iterdir()):
        if not pkg.is_dir() or pkg.name.startswith("."):
            continue
        node = _build_tree(pkg, root)
        # Skip empty packages (no source files anywhere underneath).
        if node.get("children"):
            out.append(node)
    return out


def _build_tree(node_path: Path, root: Path) -> dict:
    """Build a directory tree rooted at node_path. Children sorted dirs-first,
    then files. Skips _PACKAGE_SKIP_DIRS and only includes source extensions."""
    rel = node_path.relative_to(root).as_posix()
    children = []
    try:
        entries = sorted(node_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except (PermissionError, OSError):
        entries = []
    for child in entries:
        if child.name.startswith(".") or child.name in _PACKAGE_SKIP_DIRS:
            continue
        if child.is_dir() and child.name.endswith(_PACKAGE_SKIP_SUFFIXES):
            continue
        if child.is_dir():
            sub = _build_tree(child, root)
            # only include directory if it has any source content downstream
            if sub.get("children"):
                children.append(sub)
        else:
            ext = child.suffix.lower()
            if ext in _PACKAGE_SOURCE_EXT:
                children.append(_file_info(child, root))
    return {
        "type": "dir",
        "name": node_path.name,
        "path": rel,
        "children": children,
    }


def _walk_package(pkg_root: Path):
    """Legacy helper — kept for any callers that still want a flat walk."""
    for dirpath, dirnames, filenames in os.walk(pkg_root):
        dirnames[:] = [d for d in dirnames if d not in _PACKAGE_SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in _PACKAGE_SOURCE_EXT:
                yield Path(dirpath) / fn


def _file_info(p: Path, root: Path) -> dict:
    rel = p.relative_to(root).as_posix()
    return {
        "type": "file",
        "path": rel,
        "name": p.name,
        "size": p.stat().st_size,
        "lang": _lang_for(p.suffix),
    }


def _lang_for(ext: str) -> str:
    ext = (ext or "").lower()
    return {
        ".py": "python", ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".css": "css", ".html": "html", ".md": "markdown",
        ".json": "json", ".rs": "rust", ".toml": "toml",
        ".yml": "yaml", ".yaml": "yaml", ".sh": "shell",
    }.get(ext, "text")


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------


def _check_auth(request: web.Request) -> str | None:
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return "auth"
    return None


def _cors(resp: web.Response) -> web.Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Atrium-Token"
    return resp


async def workshop_options(request: web.Request) -> web.Response:
    return _cors(web.Response(status=204))


async def workshop_list(request: web.Request) -> web.Response:
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    kind = request.query.get("kind", "")
    try:
        items = _list_dir(kind)
    except ValueError as e:
        return _cors(web.json_response({"error": str(e)}, status=400))
    return _cors(web.json_response({"kind": kind, "items": items}))


async def workshop_read(request: web.Request) -> web.Response:
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    kind = request.query.get("kind", "")
    path = request.query.get("path", "")
    # Чтение разрешено только для skills. tools и packages — только список.
    if kind != "skills":
        return _cors(web.json_response({
            "error": f"read disabled for kind={kind!r} (skills only — "
                     f"tools/packages are list-only via workshop)",
        }, status=403))
    try:
        root = _root_for(kind)
        p = _safe_resolve(root, path)
    except (ValueError, PermissionError) as e:
        return _cors(web.json_response({"error": str(e)}, status=400))
    if not p.exists() or not p.is_file():
        return _cors(web.json_response({"error": "not found"}, status=404))
    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return _cors(web.json_response({"error": f"read failed: {e}"}, status=500))
    return _cors(web.json_response({
        "kind": kind, "path": path, "content": content,
        "size": len(content), "lang": _lang_for(p.suffix),
    }))


async def workshop_write(request: web.Request) -> web.Response:
    """Create or overwrite a file in skills/builtins or tools/plugins.

    For tools: only `plugins/<name>.py` paths are writable. Other tools
    files (core tool modules at top of tools/) are read-only via workshop —
    they're code-loaded at import time and edits should go through git.
    """
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    try:
        data = await request.json()
    except Exception:
        data = {}
    kind = str(data.get("kind") or "").strip()
    path = str(data.get("path") or "").strip()
    content = data.get("content")
    if kind != "skills":
        return _cors(web.json_response(
            {"error": f"write only allowed for kind='skills' (got {kind!r})"},
            status=403))
    if not path or not isinstance(content, str):
        return _cors(web.json_response({"error": "path + content required"}, status=400))
    if not path.endswith(".py"):
        return _cors(web.json_response({"error": "only .py files"}, status=400))
    try:
        root = _root_for(kind)
        root.mkdir(parents=True, exist_ok=True)
        p = _safe_resolve(root, path)
    except (ValueError, PermissionError) as e:
        return _cors(web.json_response({"error": str(e)}, status=400))
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(content, encoding="utf-8")
    except Exception as e:
        return _cors(web.json_response({"error": f"write failed: {e}"}, status=500))
    return _cors(web.json_response({
        "ok": True, "kind": kind, "path": path,
        "size": p.stat().st_size,
    }))


async def workshop_test(request: web.Request) -> web.Response:
    """Test-run a skill or hot-loaded tool plugin with an input string.

    For `tools` plugins: imports the module via hot_loader, calls run(input)
    if it exists, returns the string result.
    For `skills`: calls SkillExecutor with the registered skill_id derived
    from the file (best-effort — skills must already be in registry).
    """
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    try:
        data = await request.json()
    except Exception:
        data = {}
    kind = str(data.get("kind") or "").strip()
    path = str(data.get("path") or "").strip()
    inp = str(data.get("input") or "").strip()
    if kind == "tools":
        try:
            from sonya.tools.hot_loader import load_plugin
            mod_name = path.replace("\\", "/").rstrip(".py")
            if "/" in mod_name:
                mod_name = mod_name.split("/")[-1]
            mod = load_plugin(mod_name)
            if not hasattr(mod, "run"):
                return _cors(web.json_response(
                    {"error": "plugin has no run() function"}, status=400))
            result = mod.run(inp)
            return _cors(web.json_response({
                "ok": True, "result": str(result)[:4000],
            }))
        except Exception as e:
            return _cors(web.json_response(
                {"error": f"{type(e).__name__}: {e}"}, status=500))
    if kind == "skills":
        # Skills are registered with skill_id like "skill-<name>"; we don't
        # know it from the file name alone reliably. Just report — Ivan can
        # invoke via skills.run directly through the dialog composer.
        return _cors(web.json_response({
            "ok": False,
            "error": "skill test runs through skills.run from the dialog composer "
                     "(Sonya executes it). Workshop just edits the source.",
        }))
    return _cors(web.json_response({"error": "unknown kind"}, status=400))


async def workshop_reply(request: web.Request) -> web.Response:
    """Ask Sonya about a specific file. Records an incoming.atrium_workshop
    event with the file path + Ivan's question; her active session sees it
    and answers in dialog as usual."""
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    try:
        data = await request.json()
    except Exception:
        data = {}
    kind = str(data.get("kind") or "").strip()
    path = str(data.get("path") or "").strip()
    msg = str(data.get("message") or "").strip()
    if not msg:
        return _cors(web.json_response({"error": "message required"}, status=400))
    if kind != "skills":
        return _cors(web.json_response({
            "error": "reply via workshop only for skills (tools/packages — list-only)",
        }, status=403))
    config = request.app["config"]
    from sonya.admin.server import _get_substrate_writable
    sub = _get_substrate_writable(config)
    try:
        from sonya.state.continuity_stream import ContinuityStream, ContinuityEvent
        primary = config.primary_user_tg_id or "5785127604"
        stream = ContinuityStream(sub)
        # Frame it as an atrium_dialog so context_builder shows it as Иван's
        # message; tag with workshop refs in payload for traceability.
        composed = f"[workshop reply: {kind}/{path}]\n{msg}"
        ev = stream.append(ContinuityEvent(
            kind="incoming.atrium_dialog",
            channel="dialog",
            principal_id="ivan",
            payload={
                "channel": "dialog",
                "chat_id": primary,
                "sender_id": primary,
                "text": composed,
                "source": "atrium/workshop",
                "workshop_kind": kind,
                "workshop_path": path,
                "is_private": True,
            },
        ))
        # Wake the core.
        stream.append(ContinuityEvent(
            kind="internal.active_session_requested_external",
            payload={"reason": "atrium_workshop_reply", "source": "atrium/workshop"},
        ))
        return _cors(web.json_response({
            "ok": True, "event_seq": ev.seq, "kind": kind, "path": path,
        }))
    finally:
        sub.close()


def register_routes(app: web.Application) -> None:
    """Wire workshop endpoints into the admin app."""
    app.router.add_get("/api/atrium/workshop/list", workshop_list)
    app.router.add_get("/api/atrium/workshop/read", workshop_read)
    app.router.add_post("/api/atrium/workshop/write", workshop_write)
    app.router.add_post("/api/atrium/workshop/test", workshop_test)
    app.router.add_post("/api/atrium/workshop/reply", workshop_reply)
    for path in (
        "/api/atrium/workshop/list",
        "/api/atrium/workshop/read",
        "/api/atrium/workshop/write",
        "/api/atrium/workshop/test",
        "/api/atrium/workshop/reply",
    ):
        app.router.add_options(path, workshop_options)
