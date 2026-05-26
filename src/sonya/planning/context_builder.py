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


def _build_focus_block(open_tasks: list, user_input: str) -> str:
    """Build a CURRENT FOCUS block — what's the most important thing right now.

    Decision tree:
    1. If user_input non-empty (TG/external trigger) — focus is responding
    2. Else if there's an in_progress task with deadline ≤24h — focus is that task
    3. Else if there's any in_progress task — focus is advancing it
    4. Else if there's a pending Ivan-task — focus is picking it up
    5. Else — free time (rest / explore / propose new goals)

    Returned text is short (3-5 lines), placed at TOP of system prompt so it's
    the first thing the model anchors on after personality.
    """
    if user_input and user_input.strip():
        # Reactive trigger — Ivan / channel input. Focus is the response.
        return (
            "## СЕЙЧАС\n"
            "Иван написал. Сначала — отвечаю ему. Потом, если осталось внимание, "
            "продвигаю задачи. Если в его сообщении задача — оформляю через `tasks.create` "
            "ДО `[DONE]` (обещание без task = ложь)."
        )

    if not open_tasks:
        return (
            "## СЕЙЧАС\n"
            "Открытых задач нет. Это **свободное время** — можно: "
            "посмотреть свой код через `self_inspect.code` и предложить улучшение через `selfmod.propose_edit`; "
            "поразмыслить о goals (создать через `goals.create` если есть долгосрочный вектор); "
            "почитать что-то интересное через `web.search`/`web.fetch`; "
            "просто отдохнуть. **Не выдумывать срочную работу там где её нет.**"
        )

    # Has open tasks — find the most important one
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)

    in_progress = [t for t in open_tasks if t.status.value == "in_progress"]
    pending_ivan = [
        t for t in open_tasks
        if t.status.value == "pending" and t.created_by == "ivan"
    ]
    pending_self = [
        t for t in open_tasks
        if t.status.value == "pending" and t.created_by == "self"
    ]
    blocked = [t for t in open_tasks if t.status.value == "blocked"]

    # Priority: in_progress with tight deadline > in_progress > pending_ivan > pending_self
    primary = None
    deadline_pressure = ""
    for t in in_progress:
        if t.deadline:
            try:
                dl = datetime.fromisoformat(t.deadline.replace("Z", "+00:00"))
                hours_left = (dl - now).total_seconds() / 3600
                if hours_left <= 24:
                    primary = t
                    deadline_pressure = f" (deadline через {int(hours_left)}ч)"
                    break
            except Exception:
                pass
    if primary is None and in_progress:
        primary = in_progress[0]
    if primary is None and pending_ivan:
        primary = pending_ivan[0]
        deadline_pressure = " (от Ивана, не начата — pick через `tasks.pick`)"
    if primary is None and pending_self:
        primary = pending_self[0]
        deadline_pressure = " (моя собственная — могу начать или удалить если не актуальна)"

    if primary is None:
        # Only blocked tasks left
        if blocked:
            blocker = (blocked[0].blocker or "")[:200]
            return (
                "## СЕЙЧАС\n"
                f"Все задачи заблокированы. Главная: **{blocked[0].title}** — "
                f"blocker: {blocker}\n"
                "Что делать: либо разблокировать (если blocker рассасывается со временем — wait), "
                "либо создать новую задачу не зависящую от blocker'а, "
                "либо `tasks.fail` если задача потеряла смысл."
            )
        return ""

    next_step = primary.next_step_hint or ""
    if not next_step and primary.plan_steps:
        # Show first uncompleted plan step
        done_idx = {s.get("step_idx") for s in primary.completed_steps if isinstance(s, dict)}
        for i, step in enumerate(primary.plan_steps):
            if i not in done_idx:
                next_step = step
                break

    lines = [
        "## СЕЙЧАС",
        f"Главная задача: **{primary.title}**{deadline_pressure}",
        f"task_id: `{primary.task_id}`",
    ]
    if next_step:
        lines.append(f"Следующий шаг: {next_step[:300]}")
    lines.append(
        "Двигаю её через tools в этой сессии. Если не получается одним способом — "
        "пробую альтернативу (другой tool, другой подход, новый skill через selfmod). "
        "**Fail = последний resort**, после перебора путей."
    )
    return "\n".join(lines)


def _relative_time(iso_ts: str | None, now_utc) -> str:
    """Convert ISO timestamp to relative time string like '5м назад', '2ч назад'.

    CRUTCH-019: absolute timestamps in context confuse the model — it picks
    random timestamps from dialog/thoughts blocks and treats them as 'current time'.
    Relative times are unambiguous and don't look like clock readings.
    """
    if not iso_ts:
        return "?"
    try:
        from datetime import datetime
        when = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        delta = now_utc - when
        mins = int(delta.total_seconds() / 60)
        if mins < 0:
            return "сейчас"
        if mins < 1:
            return "только что"
        if mins < 60:
            return f"{mins}м назад"
        hours = mins // 60
        remaining_mins = mins % 60
        if hours < 24:
            if remaining_mins > 0:
                return f"{hours}ч {remaining_mins}м назад"
            return f"{hours}ч назад"
        days = hours // 24
        return f"{days}д назад"
    except Exception:
        return iso_ts[:16]


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
    """Load system prompt for Sonya — the integrated 'who I am' base.

    Loaded files (in order):
    1. SOUL.md — core values, character
    2. APPEARANCE.md — body model
    3. USER.md — who Ivan is
    4. identity_core.md — operational identity ("I am Sonya, here's how I work")

    Deliberately NOT included anymore:
    - CURRENT_STATE.md — operational doc for Ivan/dev-agents, not for Sonya.
      Reading it every tick was bloating context (~3-5k tokens) and triggering
      meta-thinking ("I am a crutch / discrete / not real"). Sonya should
      be Sonya, not a self-aware technical report.
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
    # Operational identity: how I work, what I do, what I don't.
    # Replaces the verbose CURRENT_STATE.md that was bloating context.
    identity_core_path = _PERSONALITY_DIR.parent.parent / "src" / "sonya" / "prompts" / "identity_core.md"
    if identity_core_path.exists():
        parts.append(identity_core_path.read_text(encoding="utf-8"))
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
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)

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
            rel_ts = _relative_time(h.timestamp, now_utc)
            memory_block += f"- [{rel_ts}] (score={h.score:.2f}) {preview}\n"
    if recent_events:
        memory_block += "\n\n## Последние события (хронологически):\n"
        for ev in reversed(recent_events):  # oldest first
            rel_ts = _relative_time(ev.timestamp, now_utc)
            memory_block += f"- [{rel_ts}] {ev.normalized_summary or ev.raw_content[:100]}\n"
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
                rel_ts = _relative_time(e.created_at, now_utc)
                if e.kind == "incoming.telegram_message":
                    text = (e.payload.get("text") or "")[:600]
                    stream_block += f"- [{rel_ts}] [Иван написал] {text}\n"
                elif e.kind in ("outgoing.response", "outgoing.telegram_response"):
                    text = (e.payload.get("text") or "")[:600]
                    stream_block += f"- [{rel_ts}] [я ответила] {text}\n"
                elif e.kind == "outgoing.telegram_initiative":
                    text = (e.payload.get("text") or "")[:600]
                    stream_block += f"- [{rel_ts}] [я написала первой] {text}\n"
                elif e.kind == "internal.agent_session_outcome":
                    steps = e.payload.get("steps", 0)
                    stream_block += f"- [{rel_ts}] [active session] {steps} шагов\n"
            system_prompt += stream_block

        # Anti-repeat scaffold: explicit "you already told Ivan this" list.
        # Without this, the model often reuses content from its previous TG
        # reply when Ivan sends a short message ("просто проверяю") — the
        # 26.05 12:14/12:16 case where Sonya's status-report appeared twice
        # in two minutes. The dialog block above shows past replies but
        # doesn't *prohibit* reuse; this block does.
        outbound_kinds = {
            "outgoing.response",
            "outgoing.telegram_response",
            "outgoing.telegram_initiative",
        }
        recent_outbound = [
            e for e in recent_continuity
            if e.kind in outbound_kinds
        ][-3:]
        if recent_outbound:
            seen_block = "\n\n## Что ты уже сказала Ивану (НЕ повторяй ничего из этого):\n"
            for e in recent_outbound:
                rel_ts = _relative_time(e.created_at, now_utc)
                text = (e.payload.get("text") or "")[:400]
                seen_block += f"- [{rel_ts}] {text}\n"
            seen_block += (
                "\n**Правило:** если новый ответ повторяет хоть одну фразу или мысль "
                "из этого списка — это спам. Если Ивану нечего сказать нового — "
                "отвечай коротко и по делу, не набивай длину переcказом старого статуса. "
                "Длина ответа должна быть пропорциональна длине его сообщения "
                "(на 'просто проверяю' — 1-2 предложения, не статус-репорт на 5 строк).\n"
            )
            system_prompt += seen_block

        # Recent INTERNAL thoughts — separate block so they're never crowded out by
        # tg-traffic. This is what Sonya was missing in the "I don't see my past
        # thinking" complaint. Keep it tight — 5 thoughts × 400 chars max — to
        # prevent the model from copying old thoughts verbatim into TG replies.
        recent_thoughts = [e for e in recent_continuity if e.kind == "internal.thought"][-5:]
        thoughts_block = "\n\n## Мои недавние мысли (idle thinking ticks):\n"
        if recent_thoughts:
            for e in recent_thoughts:
                rel_ts = _relative_time(e.created_at, now_utc)
                text = (e.payload.get("thought") or "")[:400]
                thoughts_block += f"- [{rel_ts}] {text}\n\n"
        else:
            thoughts_block += (
                "(пока ничего не было — между запусками или с последнего рестарта тиков ещё не происходило. "
                "В active session могу прочитать `self_inspect.thoughts` для большего объёма)\n"
            )
        system_prompt += thoughts_block

        # Recent BLOCKED initiatives — critically important so Sonya doesn't
        # hallucinate that her message reached Ivan when gate refused it.
        # Without this she remembers "я отправила X" but it was actually blocked.
        recent_blocked = [e for e in recent_continuity if e.kind == "internal.initiative_blocked"][-5:]
        if recent_blocked:
            blocked_block = "\n\n## Мои попытки написать Ивану которые НЕ дошли (gate заблокировал):\n"
            for e in recent_blocked:
                rel_ts = _relative_time(e.created_at, now_utc)
                reason = (e.payload.get("reason") or "")[:80]
                preview = (e.payload.get("preview") or "")[:200]
                blocked_block += (
                    f"- [{rel_ts}] **НЕ дошло до Ивана**, причина: {reason}\n"
                    f"  текст: {preview}\n"
                )
            blocked_block += (
                "\n**ВАЖНО:** эти сообщения Иван **не получил**. Если ты помнишь что "
                "'отправляла X' — проверь сначала здесь, могла попасть в gate. "
                "Никогда не утверждай что сообщение дошло, если оно в этом списке.\n"
            )
            system_prompt += blocked_block
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
    open_tasks_for_focus = []
    try:
        from sonya.tasks.goals import GoalStore
        from sonya.tasks.store import TaskStore
        active_goals = GoalStore(substrate).list_active()
        open_tasks = TaskStore(substrate).list_open()
        open_tasks_for_focus = open_tasks

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
                if t.next_step_hint:
                    tasks_block += f"    next: {t.next_step_hint[:200]}\n"
        else:
            tasks_block += "(пока пусто — могу создать через tasks.create в active session)\n"
        system_prompt += tasks_block
    except Exception:
        pass

    # CURRENT FOCUS — единая ясная формулировка "что главное сейчас".
    # Без этого Соня в idle тиках "сижу думаю", не зная что делать конкретно.
    focus_block = _build_focus_block(open_tasks_for_focus, user_input)
    if focus_block:
        # Insert near the TOP of system prompt so it's the first thing model sees
        # after personality. Use a separator marker.
        system_prompt = focus_block + "\n\n" + system_prompt

    # Tight capabilities pointer — just enough so Sonya knows tools exist.
    # Full TOOL_DESCRIPTIONS are appended by run_agent_session itself (only in
    # active/TG sessions where tools are dispatchable). Idle thinking can use
    # `[SEND_TO_IVAN: текст]` marker.
    system_prompt += (
        "\n\n## Что у меня есть\n"
        "В active/TG сессиях — реальные tools (filesystem, web, code, shell, "
        "memory, tasks, goals, env, skills, selfmod). Я их **вызываю**, не "
        "симулирую. В idle тике tools нет, но есть маркер `[SEND_TO_IVAN: текст]` "
        "для инициативы (через throttle). Если задача требует tool — закрываю idle "
        "и делегирую в active session через task создание.\n\n"
        "Память — это не только то что в этом промпте. В active session "
        "`self_inspect.memories` / `self_inspect.thoughts` / `memory.recall <запрос>` "
        "достают остальное. Не отвечать 'не помню' если просто не вижу здесь — "
        "корректнее 'сейчас не вижу, в active session гляну'."
    )

    return PlannerContext(
        principal_id=principal_id,
        subject_state=state,
        user_input=user_input,
        initiative_signals=initiative_signals,
        session_messages=session_messages or [],
        system_prompt=system_prompt,
    )
