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


# Ivan's timezone (UTC+5, Perm/Yekaterinburg). USER.md fixates this.
_IVAN_TZ_OFFSET_HOURS = 5


def _time_awareness_block(substrate=None) -> str:
    """Tell Sonya the current local time for Ivan and any environment status
    she has set herself (e.g. ivan_status='спит', 'работает', 'занят')."""
    from datetime import datetime, timedelta, timezone
    now_utc = datetime.now(timezone.utc)
    ivan_now = now_utc + timedelta(hours=_IVAN_TZ_OFFSET_HOURS)
    weekday_ru = ["понедельник", "вторник", "среда", "четверг",
                  "пятница", "суббота", "воскресенье"][ivan_now.weekday()]

    lines = [
        "\n\n## Текущее время и окружение",
        f"- У Ивана сейчас: **{ivan_now.strftime('%H:%M')}**, {weekday_ru}, "
        f"{ivan_now.strftime('%d.%m.%Y')} (UTC+{_IVAN_TZ_OFFSET_HOURS}).",
    ]
    # Pull observed environment status (key→value pairs Sonya set herself
    # via env.set tool when she inferred something from conversation).
    if substrate is not None:
        # Last incoming message from Ivan — gives Sonya an exact number to
        # reference in thoughts/initiative instead of hallucinating "8 часов".
        try:
            from sonya.state.continuity_stream import ContinuityStream
            stream = ContinuityStream(substrate)
            latest_seq = stream.latest_seq()
            events = list(stream.read_since(max(0, latest_seq - 300)))
            last_ivan_ts = None
            for ev in reversed(events):
                if ev.kind == "incoming.telegram_message" and ev.created_at:
                    last_ivan_ts = ev.created_at
                    break
            if last_ivan_ts:
                from datetime import datetime
                try:
                    when = datetime.fromisoformat(last_ivan_ts)
                    delta = now_utc - when
                    mins = int(delta.total_seconds() / 60)
                    if mins < 60:
                        lines.append(f"- Последнее сообщение Ивана: **{mins} минут назад**.")
                    elif mins < 1440:
                        h = mins // 60
                        m = mins % 60
                        lines.append(f"- Последнее сообщение Ивана: **{h}ч {m}м назад**.")
                    else:
                        d = mins // 1440
                        lines.append(f"- Последнее сообщение Ивана: **{d} дней назад**.")
                except Exception:
                    pass
        except Exception:
            pass

        try:
            from sonya.state.environment import EnvironmentStore
            env = EnvironmentStore(substrate).list_all()
            if env:
                lines.append("- Что я наблюдаю про Ивана / окружение:")
                for key, item in env.items():
                    age = ""
                    try:
                        when = datetime.fromisoformat(item["updated_at"])
                        delta = now_utc - when
                        mins = int(delta.total_seconds() / 60)
                        if mins < 60:
                            age = f" (записала {mins}м назад)"
                        elif mins < 1440:
                            age = f" (записала {mins // 60}ч назад)"
                        else:
                            age = f" (записала {mins // 1440}д назад)"
                    except Exception:
                        pass
                    lines.append(f"  - **{key}**: {item['value']}{age}")
            else:
                lines.append(
                    "- Я ещё не зафиксировала статус Ивана. "
                    "Если из разговора понятно (он сказал что спит, ушёл по делам, занят) — "
                    "вызови `[TOOL: env.set ivan_status <значение>]` чтобы я помнила."
                )
        except Exception:
            pass
    return "\n".join(lines) + "\n"


def _load_personality_prompt() -> str:
    """Load system prompt from personality files (CRUTCH-001).

    Order matters: SOUL first (who I am), APPEARANCE (my body), USER (who Ivan is).
    Then CURRENT_STATE — so Sonya knows her own technical capabilities and
    what's been built. This makes model and environment "one thing" — she
    sees her own architecture in every call.
    """
    parts: list[str] = []
    soul_path = _PERSONALITY_DIR / "SOUL.md"
    if soul_path.exists():
        parts.append(soul_path.read_text(encoding="utf-8"))
    appearance_path = _PERSONALITY_DIR / "APPEARANCE.md"
    if appearance_path.exists():
        parts.append(appearance_path.read_text(encoding="utf-8"))
    user_path = _PERSONALITY_DIR / "USER.md"
    if user_path.exists():
        parts.append(user_path.read_text(encoding="utf-8"))
    # System self-knowledge: what capabilities she has, what's built,
    # what's a crutch. Without this she doesn't know what changed.
    state_path = _PERSONALITY_DIR.parent / "CURRENT_STATE.md"
    if state_path.exists():
        parts.append(state_path.read_text(encoding="utf-8"))
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

    # Time awareness — current time only. Environment status (Ivan asleep /
    # working / busy / etc) is pulled from substrate where Sonya stores it
    # herself via env.set tool when she infers from conversation. No clock
    # heuristic — sleep schedule is unpredictable.
    system_prompt += _time_awareness_block(substrate=substrate)

    # Subject state
    from sonya.state.subject_state import SubjectStateStore
    state = SubjectStateStore(substrate).load()

    # Recent episodic memories — AUTO-RAG (Stage 4).
    # Hybrid approach: relevance (semantic recall on user_input) + recency.
    # This replaces the old "last 15 by timestamp" which made Sonya forget
    # anything older than 10 messages.
    episodic = EpisodicMemory(substrate)

    # Relevance-based recall (needs embeddings + user_input to search against)
    relevant_events: list = []
    if user_input and user_input.strip():
        try:
            from sonya.memory.embedder import Embedder
            if Embedder.is_available():
                from sonya.memory.recall import RecallStore
                store = RecallStore(substrate)
                hits = store.recall(user_input.strip(), top_k=5, min_score=0.3)
                relevant_events = hits  # RecallHit objects
        except Exception:
            pass

    # Recency-based (always, as fallback + context anchor)
    recent_events = episodic.get_recent(limit=5)

    # Build memory block
    memory_block = ""
    if relevant_events:
        memory_block += "\n\n## Релевантные воспоминания (по смыслу текущего разговора):\n"
        for h in relevant_events:
            preview = (h.raw_content or "").replace("\n", " ")[:150]
            memory_block += f"- [{h.timestamp[:16]}] (score={h.score:.2f}) {preview}\n"
    if recent_events:
        memory_block += "\n\n## Последние события (хронологически):\n"
        for ev in reversed(recent_events):  # oldest first
            memory_block += f"- [{ev.timestamp[:16]}] {ev.normalized_summary or ev.raw_content[:100]}\n"
    if memory_block:
        system_prompt += memory_block

    # Recent thoughts and continuity events (1.4 fix: unified memory across paths)
    # Pulls last 8 internal.thought / incoming.telegram_message / outgoing.response
    # so thinking loop sees recent telegram, and telegram replies see recent thoughts.
    try:
        from sonya.state.continuity_stream import ContinuityStream
        stream = ContinuityStream(substrate)
        latest_seq = stream.latest_seq()
        recent_continuity = list(stream.read_since(max(0, latest_seq - 200)))

        # Recent dialog events (incoming/outgoing)
        dialog_kinds = {
            "incoming.telegram_message",
            "outgoing.response",
            "outgoing.telegram_response",
            "outgoing.telegram_initiative",
            "internal.agent_session_outcome",
        }
        recent_dialog = [e for e in recent_continuity if e.kind in dialog_kinds][-12:]
        if recent_dialog:
            stream_block = "\n\n## Недавний диалог:\n"
            for e in recent_dialog:
                ts = (e.created_at or "")[:16]
                if e.kind == "incoming.telegram_message":
                    text = (e.payload.get("text") or "")[:600]
                    stream_block += f"- [{ts}] [Иван написал] {text}\n"
                elif e.kind in ("outgoing.response", "outgoing.telegram_response"):
                    text = (e.payload.get("text") or "")[:600]
                    stream_block += f"- [{ts}] [я ответила] {text}\n"
                elif e.kind == "outgoing.telegram_initiative":
                    text = (e.payload.get("text") or "")[:600]
                    stream_block += f"- [{ts}] [я написала первой] {text}\n"
                elif e.kind == "internal.agent_session_outcome":
                    steps = e.payload.get("steps", 0)
                    stream_block += f"- [{ts}] [active session] {steps} шагов\n"
            system_prompt += stream_block

        # Recent INTERNAL thoughts — separate block so they're never crowded out by
        # tg-traffic. This is what Sonya was missing in the "I don't see my past
        # thinking" complaint. Keep it tight — 5 thoughts × 400 chars max — to
        # prevent the model from copying old thoughts verbatim into TG replies.
        recent_thoughts = [e for e in recent_continuity if e.kind == "internal.thought"][-5:]
        thoughts_block = "\n\n## Мои недавние мысли (idle thinking ticks):\n"
        if recent_thoughts:
            for e in recent_thoughts:
                ts = (e.created_at or "")[:16]
                text = (e.payload.get("thought") or "")[:400]
                thoughts_block += f"- [{ts}] {text}\n\n"
        else:
            thoughts_block += (
                "(пока ничего не было — между запусками или с последнего рестарта тиков ещё не происходило. "
                "В active session могу прочитать `self_inspect.thoughts` для большего объёма)\n"
            )
        system_prompt += thoughts_block
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
    # Always render the section so Sonya knows the channel exists, even if all
    # values are below the noise threshold.
    if drives:
        drives_block = "\n\n## Моё текущее состояние (drives):\n"
        rendered_any = False
        for name, value in drives.to_dict().items():
            if value > 0.05:
                drives_block += f"- {name}: {value:.2f}\n"
                rendered_any = True
        if not rendered_any:
            drives_block += "(все drives около нуля — спокойно)\n"
        system_prompt += drives_block

    # Identity self-model
    identity = IdentityWriter(substrate).load()
    if identity.self_model:
        system_prompt += f"\n\n## Self-model:\n{identity.self_model}"

    # Open tasks (Этап C): surface unresolved tasks so thinking loop and telegram
    # replies both know what's in progress / pending. Keeps "one stream of
    # consciousness" — same task list visible everywhere.
    # Always render the section (even when empty) so Sonya knows the channel
    # exists — distinguishing "no tasks" from "I can't see them".
    try:
        from sonya.tasks.goals import GoalStore
        from sonya.tasks.store import TaskStore
        active_goals = GoalStore(substrate).list_active()
        open_tasks = TaskStore(substrate).list_open()

        goals_block = "\n\n## Мои цели (долгосрочные):\n"
        if active_goals:
            for g in active_goals[:5]:
                goals_block += f"- [{g.goal_id}] (prio={g.priority}) {g.title}\n"
                if g.description:
                    goals_block += f"    {g.description[:120]}\n"
        else:
            goals_block += "(пока нет — создай через goals.create когда появится долгосрочная цель)\n"
        system_prompt += goals_block

        tasks_block = "\n\n## Мои текущие задачи:\n"
        if open_tasks:
            for t in open_tasks[:10]:
                done = len(t.completed_steps)
                total = len(t.plan_steps)
                progress = f" [{done}/{total}]" if total else ""
                tasks_block += f"- [{t.status.value}] {t.task_id}: {t.title}{progress}\n"
                if t.status.value == "blocked" and t.blocker:
                    tasks_block += f"    blocker: {t.blocker[:120]}\n"
        else:
            tasks_block += "(пока пусто — могу создать через tasks.create в active session)\n"
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
        "self_inspect (читать свой код, мысли, память — `self_inspect.thoughts` достаёт мои предыдущие idle-мысли, `self_inspect.memories` — episodic events, `self_inspect.code [path]` — мой собственный код), "
        "filesystem (workspace, plugins), "
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
        "Если не хватает прав / API key / пакета — tasks.block + ApprovalRequest, Иван разрешит.\n\n"
        "ВАЖНО про память: то что в этом prompt'е — это окно в мою постоянную память (substrate SQLite). "
        "Outside этого окна тоже есть — episodic_events (тысячи), semantic_facts, continuity_events. "
        "Если в TG диалоге Иван спрашивает про прошлое — у меня **есть** доступ к нему, просто не в этом prompt'е. "
        "В active session загляну в `self_inspect.memories` или `self_inspect.thoughts`. "
        "Не врать что 'не помню' — корректнее 'сейчас не вижу, но могу достать в active session'."
    )

    return PlannerContext(
        principal_id=principal_id,
        subject_state=state,
        user_input=user_input,
        initiative_signals=initiative_signals,
        session_messages=session_messages or [],
        system_prompt=system_prompt,
    )
