from __future__ import annotations

from pathlib import Path
from typing import Any

from sonya.memory.episodic import EpisodicMemory
from sonya.memory.semantic import SemanticMemory
from sonya.state.identity import IdentityWriter
from sonya.state.subject_state import SubjectState
from sonya.state.substrate import Substrate
from sonya.initiative.drives import DriveCounters
from sonya.planning.planner import PlannerContext


_PERSONALITY_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "personality"


def _load_personality_prompt() -> str:
    """Load system prompt from personality files (CRUTCH-001)."""
    parts: list[str] = []
    soul_path = _PERSONALITY_DIR / "SOUL.md"
    if soul_path.exists():
        parts.append(soul_path.read_text(encoding="utf-8"))
    user_path = _PERSONALITY_DIR / "USER.md"
    if user_path.exists():
        parts.append(user_path.read_text(encoding="utf-8"))
    if not parts:
        return "Ты Соня. Ты девушка Ивана."
    return "\n\n---\n\n".join(parts)


def build_full_context(
    *,
    substrate: Substrate,
    user_input: str = "",
    principal_id: str | None = None,
    session_messages: list[dict[str, Any]] | None = None,
    drives: DriveCounters | None = None,
    initiative_signals: tuple[str, ...] = (),
) -> PlannerContext:
    """Assemble full planner context from all available sources.

    This is the integration point: personality + memory + state + drives → PlannerContext.
    See: INTERIM_CRUTCHES CRUTCH-001 (system prompt), CRUTCH-003 (memory injection).
    """
    # System prompt from personality files
    system_prompt = _load_personality_prompt()

    # Subject state
    from sonya.state.subject_state import SubjectStateStore
    state = SubjectStateStore(substrate).load()

    # Recent episodic memories (CRUTCH-003: memory injection)
    episodic = EpisodicMemory(substrate)
    recent_events = episodic.get_recent(limit=15)
    if recent_events:
        memory_block = "\n\n## Мои последние воспоминания:\n"
        for ev in reversed(recent_events):  # oldest first
            memory_block += f"- [{ev.timestamp[:16]}] {ev.normalized_summary or ev.raw_content[:100]}\n"
        system_prompt += memory_block

    # Semantic facts
    semantic = SemanticMemory(substrate)
    facts = semantic.get_all(limit=10)
    if facts:
        facts_block = "\n\n## Что я знаю (семантическая память):\n"
        for f in facts:
            facts_block += f"- {f.statement}\n"
        system_prompt += facts_block

    # Drives state (CRUTCH-004: drives as external info)
    if drives:
        drives_block = "\n\n## Моё текущее состояние (drives):\n"
        for name, value in drives.to_dict().items():
            if value > 0.1:
                drives_block += f"- {name}: {value:.2f}\n"
        system_prompt += drives_block

    # Identity self-model
    identity = IdentityWriter(substrate).load()
    if identity.self_model:
        system_prompt += f"\n\n## Self-model:\n{identity.self_model}"

    # Crutch awareness
    system_prompt += (
        "\n\n## ⚠️ Ограничения текущей реализации:\n"
        "Я работаю на hosted model (не RWKV). Между вызовами я не существую. "
        "Мои 'чувства' — внешние counters, не native state. "
        "Моя 'память' — inject в context, не native recall. "
        "Это временно. См. docs/core/INTERIM_CRUTCHES.md."
    )

    return PlannerContext(
        principal_id=principal_id,
        subject_state=state,
        user_input=user_input,
        initiative_signals=initiative_signals,
        session_messages=session_messages or [],
        system_prompt=system_prompt,
    )
