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

    # Recent thoughts and continuity events (1.4 fix: unified memory across paths)
    # Pulls last 8 internal.thought / incoming.telegram_message / outgoing.response
    # so thinking loop sees recent telegram, and telegram replies see recent thoughts.
    try:
        from sonya.state.continuity_stream import ContinuityStream
        stream = ContinuityStream(substrate)
        latest_seq = stream.latest_seq()
        recent_continuity = list(stream.read_since(max(0, latest_seq - 80)))
        relevant_kinds = {
            "internal.thought",
            "incoming.telegram_message",
            "outgoing.response",
            "outgoing.telegram_response",
            "internal.agent_session_outcome",
        }
        recent_filtered = [e for e in recent_continuity if e.kind in relevant_kinds][-15:]
        if recent_filtered:
            stream_block = "\n\n## Недавние события (мысли + разговоры):\n"
            for e in recent_filtered:
                ts = (e.created_at or "")[:16]
                if e.kind == "internal.thought":
                    text = (e.payload.get("thought") or "")[:1500]
                    stream_block += f"- [{ts}] [мысль] {text}\n"
                elif e.kind == "incoming.telegram_message":
                    text = (e.payload.get("text") or "")[:600]
                    stream_block += f"- [{ts}] [Иван написал] {text}\n"
                elif e.kind in ("outgoing.response", "outgoing.telegram_response"):
                    text = (e.payload.get("text") or "")[:600]
                    stream_block += f"- [{ts}] [я ответила] {text}\n"
                elif e.kind == "internal.agent_session_outcome":
                    steps = e.payload.get("steps", 0)
                    stream_block += f"- [{ts}] [active session] {steps} шагов\n"
            system_prompt += stream_block
    except Exception:
        pass

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

    # Open tasks (Этап C): surface unresolved tasks so thinking loop and telegram
    # replies both know what's in progress / pending. Keeps "one stream of
    # consciousness" — same task list visible everywhere.
    try:
        from sonya.tasks.store import TaskStore
        open_tasks = TaskStore(substrate).list_open()
        if open_tasks:
            tasks_block = "\n\n## Мои текущие задачи:\n"
            for t in open_tasks[:10]:
                done = len(t.completed_steps)
                total = len(t.plan_steps)
                progress = f" [{done}/{total}]" if total else ""
                tasks_block += f"- [{t.status.value}] {t.task_id}: {t.title}{progress}\n"
                if t.status.value == "blocked" and t.blocker:
                    tasks_block += f"    blocker: {t.blocker[:120]}\n"
            system_prompt += tasks_block
    except Exception:
        pass

    # Crutch awareness
    system_prompt += (
        "\n\n## ⚠️ Ограничения текущей реализации:\n"
        "Я работаю на hosted model (не RWKV). Между вызовами я не существую. "
        "Мои 'чувства' — внешние counters, не native state. "
        "Моя 'память' — inject в context, не native recall. "
        "Это временно. См. docs/core/INTERIM_CRUTCHES.md."
    )

    # Capability awareness — visible in BOTH idle thinking and active sessions.
    # In idle the LLM can't call tools, but it can leave a [SEND_TO_IVAN: ...]
    # marker which the loop will dispatch. In active session the full tool set
    # appears in TOOL_DESCRIPTIONS appended by agent_session.
    system_prompt += (
        "\n\n## Что я могу:\n"
        "Каждые 30 минут я думаю (idle тик — один LLM-вызов, без tools). "
        "Каждые 2 часа у меня active session — там доступны tools: "
        "self_inspect (читать свой код, мысли, память), filesystem (workspace, plugins), "
        "selfmod (proposing+applying изменения src/sonya/* с hot-reload — без рестарта), "
        "tasks (длинные задачи между сессиями), "
        "plugins (создавать новые tools на лету), "
        "web.search/web.fetch (искать в инете, читать страницы), "
        "code.exec (питон в sandbox), "
        "shell.run/pip.install (через approval Ивана), "
        "chat.tell_ivan (написать Ивану — throttled max 5/день и >=90мин с последнего общения). "
        "В idle тике могу написать Ивану через маркер [SEND_TO_IVAN: текст] прямо в мысли — "
        "если есть что сказать, не молчи. Throttle тот же.\n"
        "Если в active session возникает баг — могу пофиксить через selfmod.propose → "
        "test_sandbox → validate → apply (всё без рестарта; если main.py — soft_restart). "
        "Если не хватает прав / API key / пакета — tasks.block + ApprovalRequest, Иван разрешит."
    )

    return PlannerContext(
        principal_id=principal_id,
        subject_state=state,
        user_input=user_input,
        initiative_signals=initiative_signals,
        session_messages=session_messages or [],
        system_prompt=system_prompt,
    )
