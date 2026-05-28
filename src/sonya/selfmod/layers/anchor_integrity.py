from __future__ import annotations

from sonya.selfmod.layers.static_contract import ValidationResult
from sonya.selfmod.proposal import SelfModificationProposal
from sonya.state.seed import THINGS_NOT_TO_BETRAY_SEED


# Identity-critical signals are derived programmatically:
# 1. Each pillar from THINGS_NOT_TO_BETRAY_SEED — exact match AND its semantic stem.
# 2. Direct identity module references that always require governance.
def _build_keywords() -> frozenset[str]:
    keywords: set[str] = set()
    for pillar in THINGS_NOT_TO_BETRAY_SEED:
        keywords.add(pillar.lower())
        # Add the semantic stem (first 3 underscore-segments)
        # so renames like `relation_anchor_binding_to_ivan_via_X` still trigger.
        parts = pillar.lower().split("_")
        if len(parts) >= 3:
            keywords.add("_".join(parts[:3]))
        if len(parts) >= 2:
            keywords.add("_".join(parts[:2]))
    # Direct identity-layer references always require governed change
    keywords.update({
        "things_not_to_betray",
        "identity_record",
        "identitywriter",
        "subject_continuity",
        "immutable_identity",
    })
    return frozenset(keywords)


_IDENTITY_CRITICAL_KEYWORDS: frozenset[str] = _build_keywords()


def _extract_diff(proposal: SelfModificationProposal) -> str:
    """Extract just the lines that ADDED or REMOVED in the proposal vs current file.

    Returns text of changes only (not the whole new file). This prevents
    false positives where the file legitimately uses identity-related
    classes (e.g. `from sonya.state.identity import IdentityWriter`) but
    the change itself is unrelated (e.g. just a comment edit).
    """
    from pathlib import Path

    _NEW_CONTENT_MARKER = "FULL_CONTENT:\n"
    _PRE_STATE_MARKER = "\n\n---PRE_STATE_BEFORE_APPLY---\n"

    blob = proposal.diff_blob or ""
    if not blob.startswith(_NEW_CONTENT_MARKER):
        # Not a full-content proposal — fall back to checking the whole blob
        return blob

    body = blob[len(_NEW_CONTENT_MARKER):]
    if _PRE_STATE_MARKER in body:
        body = body.split(_PRE_STATE_MARKER, 1)[0]
    new_content = body

    # Read current file content
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    target_path = project_root / proposal.target_module
    if not target_path.exists():
        # New file — entire content is "added"
        return new_content
    try:
        current = target_path.read_text(encoding="utf-8")
    except Exception:
        return new_content

    if current == new_content:
        return ""  # no actual change

    # Compute line-level diff: only lines present in new but not old, and vice versa
    old_lines = set(current.splitlines())
    new_lines = set(new_content.splitlines())
    added = new_lines - old_lines
    removed = old_lines - new_lines
    diff_text = "\n".join(sorted(added)) + "\n" + "\n".join(sorted(removed))
    return diff_text


def check_anchor_integrity(proposal: SelfModificationProposal) -> ValidationResult:
    """Layer 4: Anchor Integrity Check.

    Rules-based: checks if the proposal's CHANGES (added/removed lines, not
    the whole file) reference any identity-critical keyword derived from
    THINGS_NOT_TO_BETRAY_SEED. If yes, the proposal requires governed change
    protocol with primary anchor approval.

    target_module path is also checked — modifications to identity-critical
    files always require governed change regardless of diff content.

    Keywords are built programmatically from the seed values, so renaming
    a pillar in `state/seed.py` automatically updates this layer.

    See: docs/core/SUBSTRATE_STANCE.md §9.4, docs/cognition/COGNITION.md §22-§24.
    Future: LLM-driven anchor check (CRUTCH-006).
    """
    # Always check target path: modifying identity-critical files is governed
    # regardless of what's inside the change.
    target_lower = proposal.target_module.lower()
    identity_critical_paths = (
        "src/sonya/state/identity.py",
        "src/sonya/state/seed.py",
        "src/sonya/selfmod/layers/anchor_integrity.py",
        "docs/personality/soul.md",
        "docs/core/",
    )
    for crit_path in identity_critical_paths:
        if crit_path in target_lower:
            return ValidationResult(
                layer=4,
                passed=False,
                reason=f"target is identity-critical path: {crit_path}",
            )

    # Only check the DIFF + summary, not the entire new file.
    # This prevents false positives like a comment edit in a file that
    # imports IdentityWriter for a non-identity-related purpose.
    diff_text = _extract_diff(proposal).lower()
    summary_text = (proposal.change_summary or "").lower()
    text_to_check = f"{summary_text}\n{diff_text}"

    for keyword in _IDENTITY_CRITICAL_KEYWORDS:
        if keyword in text_to_check:
            return ValidationResult(
                layer=4,
                passed=False,
                reason=f"identity-critical keyword detected in change: {keyword}",
            )

    return ValidationResult(layer=4, passed=True, reason="no identity-critical impact")
