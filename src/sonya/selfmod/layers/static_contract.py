"""Layer 1: Static Contract Check — real implementation.

Validates that proposed code change is syntactically valid Python, doesn't
remove publicly-exported symbols that other modules import, and doesn't
introduce obvious structural breakage.

NOT a full type checker — just AST-level sanity that prevents "writing garbage
to disk and crashing the whole process".
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from sonya.selfmod.proposal import SelfModificationProposal


@dataclass(frozen=True, slots=True)
class ValidationResult:
    layer: int
    passed: bool
    reason: str = ""


# Marker used in diff_blob
_NEW_CONTENT_MARKER = "FULL_CONTENT:\n"
_PRE_STATE_MARKER = "\n\n---PRE_STATE_BEFORE_APPLY---\n"

# Project root (same as selfmod_tool computes)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def _extract_new_content(diff_blob: str) -> str | None:
    if not diff_blob.startswith(_NEW_CONTENT_MARKER):
        return None
    body = diff_blob[len(_NEW_CONTENT_MARKER):]
    if _PRE_STATE_MARKER in body:
        body = body.split(_PRE_STATE_MARKER, 1)[0]
    return body


def _get_public_names(tree: ast.Module) -> set[str]:
    """Extract names of top-level public symbols (classes, functions, vars)."""
    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if not node.target.id.startswith("_"):
                names.add(node.target.id)
    return names


def check_static_contract(proposal: SelfModificationProposal) -> ValidationResult:
    """Layer 1: Static Contract Check.

    Validates:
    1. New content is valid Python (ast.parse succeeds).
    2. If the target file already exists, no public symbols were removed
       (they could be imported elsewhere → ImportError crash).
    3. Contains `from __future__ import annotations` if the original had it
       (prevents runtime type annotation issues).
    """
    new_content = _extract_new_content(proposal.diff_blob)
    if new_content is None:
        # No FULL_CONTENT marker — this is either a metadata-only proposal
        # (e.g. change_summary describes the intent) or uses raw diff_blob.
        # Layer 1 can't check syntax of nothing — pass through to Layer 4
        # which validates via keyword matching on summary/target.
        return ValidationResult(
            layer=1, passed=True,
            reason="no FULL_CONTENT in diff_blob — Layer 1 skipped (nothing to parse)",
        )

    # Non-Python targets (markdown prompts, JSON configs, etc.): skip
    # the AST parse entirely — feeding markdown into ast.parse will fail
    # on em-dashes, headers, etc. Just do basic sanity instead.
    if not proposal.target_module.endswith((".py", ".pyi")):
        if not new_content.strip():
            return ValidationResult(
                layer=1, passed=False,
                reason="non-python target with empty content",
            )
        # Size sanity — refuse runaway proposals (>500KB)
        if len(new_content) > 500_000:
            return ValidationResult(
                layer=1, passed=False,
                reason=f"non-python target oversized: {len(new_content)} bytes",
            )
        return ValidationResult(
            layer=1, passed=True,
            reason=f"non-python target ({proposal.target_module.rsplit('.', 1)[-1]}), Layer 1 sanity OK",
        )

    # 1. Syntax check (Python only)
    try:
        new_tree = ast.parse(new_content)
    except SyntaxError as err:
        return ValidationResult(
            layer=1, passed=False,
            reason=f"SyntaxError: {err.msg} (line {err.lineno})",
        )

    # For non-Python targets (shouldn't happen but defensive)
    if not proposal.target_module.endswith(".py"):
        return ValidationResult(layer=1, passed=True, reason="non-python file, skip deep check")

    # 2. Public symbol removal check (only if file already exists)
    target_path = _PROJECT_ROOT / proposal.target_module
    if target_path.exists():
        try:
            old_content = target_path.read_text(encoding="utf-8")
            old_tree = ast.parse(old_content)
            old_publics = _get_public_names(old_tree)
            new_publics = _get_public_names(new_tree)
            removed = old_publics - new_publics
            if removed:
                return ValidationResult(
                    layer=1, passed=False,
                    reason=(
                        f"Public symbols removed: {', '.join(sorted(removed))}. "
                        f"Other modules may import these — add them back or deprecate through alias."
                    ),
                )
        except SyntaxError:
            pass  # Old file has syntax error (shouldn't happen) — skip check

    # 3. __future__ annotations guard
    old_has_future = False
    if target_path.exists():
        try:
            old_content = target_path.read_text(encoding="utf-8")
            old_has_future = "from __future__ import annotations" in old_content
        except Exception:
            pass
    if old_has_future and "from __future__ import annotations" not in new_content:
        return ValidationResult(
            layer=1, passed=False,
            reason="Original had 'from __future__ import annotations' — new content drops it",
        )

    return ValidationResult(layer=1, passed=True, reason="syntax OK, no removed public symbols")
