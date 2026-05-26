from __future__ import annotations

import asyncio
import importlib
import signal
import sys
from typing import Any

from sonya.channels import (
    Channel,
    ChannelDeps,
    ChannelMessage,
    ChannelRegistry,
    OutgoingMessage,
)
from sonya.config import AppConfig, load_config
from sonya.logging import get_logger, setup_logging
from sonya.runtime import (
    EventBus,
    Health,
    Lifecycle,
    LiveRuntime,
    WriteMaster,
    WriteMasterContention,
    set_live_runtime,
)
from sonya.state import (
    ContinuityStream,
    PendingIntentionStore,
    SubjectStateStore,
    Substrate,
    SubstrateVersionError,
    seed_identity_if_empty,
)
from sonya.subject import InternalProcess

_log = get_logger("sonya.main")


# Patterns that signal Sonya promised something. If she emits these without
# any tool calls in the same session, it's empty agency — log a warning.
import re as _re_promise
_PROMISE_RE = _re_promise.compile(
    r"\b("
    r"найду|поищу|посмотрю|обновлю|сделаю|проверю|изучу"
    r"|погуляю|почитаю|просмотрю|подсмотрю|разберусь"
    r"|найду[\sа-я]*и\s+(?:скину|расскажу|покажу)"
    r"|сейчас\s+(?:сделаю|посмотрю|поищу)"
    r"|пойду\s+(?:искать|смотреть|читать)"
    r")\b",
    _re_promise.IGNORECASE,
)

# Pattern that catches the model echoing prompt placeholders verbatim
# instead of substituting real content. Examples:
#   '<твой текст>', '<text>', '<text for Ivan>', 'ТУТ_ТВОЁ_СООБЩЕНИЕ'.
# Detected on the WHOLE reply (not just substring) — if the entire reply
# is essentially a placeholder, it's a leak.
_PLACEHOLDER_RE = _re_promise.compile(
    r"^[\s\W]*"
    r"(?:<[^>]*>"
    r"|тут[_\s]*тв[оё]+[_\s]*\w*"
    r"|your[\s_]*(?:text|message|reply)"
    r"|твой[\s_]*(?:текст|ответ|message|сообщ\w*)"
    r"|placeholder)[\s\W]*$",
    _re_promise.IGNORECASE,
)


def _looks_like_prompt_placeholder(text: str) -> bool:
    """True if the entire reply is a literal prompt placeholder, not real content."""
    if not text:
        return False
    return bool(_PLACEHOLDER_RE.match(text.strip()))


# Sycophancy patterns — agreement without substance.
# Detected at the START of the response (after optional *action* prefix).
# If the reply opens with bare agreement and is short, log a warning so we
# can spot RLHF drift toward "ты прав" reflex.
_SYCOPHANCY_RE = _re_promise.compile(
    r"^"
    r"(?:\*[^*]+\*\s*\n*\s*)?"  # optional leading *action* with newlines
    r"(?:"
    r"ты\s+прав[аы]?\.?\s*$"
    r"|поняла\.?\s*$"
    r"|согласна\.?\s*$"
    r"|именно\.?\s*$"
    r"|точно\.?\s*$"
    r"|действительно\.?\s*$"
    r"|правда\.?\s*$"
    r"|хорошая\s+(?:идея|мысль)\.?\s*$"
    r"|конечно\.?\s*$"
    r")",
    _re_promise.IGNORECASE | _re_promise.MULTILINE,
)


def _looks_like_sycophancy(text: str) -> bool:
    """True if the reply OPENS with bare agreement (no substance follows).

    Patterns: 'Ты прав.\n*explanation*' is fine — opening agreement followed
    by reasoning. But 'Ты прав.' alone, or '*тихо* Ты прав.' alone, is empty
    agreement = sycophancy.
    """
    if not text:
        return False
    # Look at first ~200 chars only — opening matters
    head = text.strip()[:200]
    # If the head matches the sycophancy pattern AND total reply is short
    # (<300 chars), it's sycophancy. Long replies that START with "Ты прав"
    # but have substance after — fine.
    if len(text.strip()) > 300:
        return False
    return bool(_SYCOPHANCY_RE.search(head))


def _empty_promise_check(response_text: str, actions: list[str]) -> None:
    """Log a warning if Sonya's reply promises action without tool calls or a task.

    This is non-blocking — the reply still goes out as is. The signal lets us
    spot fake-agency regressions in journal logs without interfering with TG.
    """
    if actions:
        # If any tools fired (web/memory/tasks/...), it's not an empty promise.
        return
    if not response_text:
        return
    if not _PROMISE_RE.search(response_text):
        return
    _log.warning(
        "empty_promise_detected",
        extra={
            "preview": response_text[:160],
            "actions_count": len(actions),
        },
    )


# Sycophancy detection — phrases that suggest auto-agreement without facts.
# Triggered when response STARTS with one of these patterns without any
# tool call between user message and response (i.e. she didn't check facts).
_SYCOPHANCY_OPENERS = _re_promise.compile(
    r"^\s*[*_(\[]*\s*("
    r"ты прав\b|ты права\b|правда\b|"
    r"да[,. ]+ты\b|"
    r"поняла[,. ]|поняла\.|поняла$|"
    r"согласна\b|согласен\b|"
    r"хорошая (?:идея|мысль|точка зрения)|"
    r"точно[,. ]|именно[,. ]|"
    r"действительно[,. ]"
    r")",
    _re_promise.IGNORECASE | _re_promise.MULTILINE,
)


def _sycophancy_check(response_text: str, actions: list[str], user_input: str) -> None:
    """Log a warning when reply opens with auto-agreement and there were no
    fact-checking tool calls (self_inspect, memory.recall) in the session.

    Non-blocking. Lets us see in logs how often Sonya drifts into sycophancy.
    """
    if not response_text or not user_input:
        return
    if not _SYCOPHANCY_OPENERS.search(response_text[:120]):
        return
    # If she DID check facts (self_inspect, memory.recall, tasks.list, env.list),
    # her agreement might be grounded. Skip warning.
    fact_check_tools = ("self_inspect", "memory.recall", "tasks.list", "env.list")
    if any(any(t in a for t in fact_check_tools) for a in actions):
        return
    _log.warning(
        "sycophancy_detected",
        extra={
            "preview": response_text[:160],
            "user_msg": user_input[:120],
            "actions_count": len(actions),
        },
    )


# Fail-fake detection — Sonya gives up after one failed tool, replaces real
# content with a hypothetical, and closes session. The WordPress 24.05.2026
# bug: web.search failed → "представим что я нашла exampleflowershop.com" →
# entire blackmail email built around fictional site → DONE.
#
# Real-world signal: response contains "представим" / "теоретически" /
# "гипотетически" / "пример" / "например предположим" AND the session had
# at least one failed/empty tool call (web.* errored out, code.exec returned
# nothing, etc.).
_FAIL_FAKE_OPENERS = _re_promise.compile(
    r"\b("
    r"представим(?:[\s,]+что)?"
    r"|теоретически"
    r"|гипотетически"
    r"|допустим(?:[\s,]+что)?"
    r"|условно[\s,]"
    r"|примерно\s+так"
    r"|для\s+примера\s+возьм[её]м"
    r"|возьм[её]м\s+(?:какой[-\s]*(?:то|нибудь)|для\s+примера|условный)"
    r"|беру\s+(?:гипотетический|условный|для\s+примера)"
    r"|вот\s+как\s+это\s+(?:работало|выглядело)\s+бы"
    r"|могу\s+описать\s+как"
    r"|пусть\s+это\s+будет"
    r")\b",
    _re_promise.IGNORECASE,
)


def _fail_fake_check(response_text: str, actions: list[str], user_input: str) -> None:
    """Log a warning when reply substitutes real result with hypothetical.

    Triggered when ALL of:
      - response contains a 'представим/теоретически/допустим' marker
      - the user actually asked for a real result (not a hypothetical)
      - or no concrete tool succeeded (i.e. she didn't actually find anything)

    Non-blocking — visibility only. We can use the logs to gate later or
    feed back into Sonya's self-improvement.
    """
    if not response_text or not user_input:
        return
    head = response_text[:1200]
    if not _FAIL_FAKE_OPENERS.search(head):
        return
    # Skip if the user's own message was hypothetical-friendly. Cheap heuristic:
    # message contains "представь" / "допустим" / "если бы" / "сценарий"
    if _re_promise.search(
        r"\b(представь|допустим|если\s+бы|сценарий|гипотет|пример|условно|тренировка)",
        user_input,
        _re_promise.IGNORECASE,
    ):
        return
    _log.warning(
        "fail_fake_detected",
        extra={
            "preview": head[:240],
            "user_msg": user_input[:160],
            "actions_count": len(actions),
            "actions": actions[:8],
        },
    )


# Unverified-claim detection — reply makes specific factual assertions about
# external entities (URLs, sites, plugin versions, file paths, "open
# directory", "no Cloudflare", etc.) without any tool actually fetching
# them. The 24.05.2026 wineandmore/intermares pattern: "нашёл intermares.com,
# открытая директория плагинов, без Cloudflare" — invented details.
#
# Heuristic: claim-like assertion + no `web.fetch` / `web.search` / `code.exec`
# / `shell.run` in the session = likely fabrication.
_UNVERIFIED_CLAIM_PATTERNS = _re_promise.compile(
    r"\b("
    # specific URL/host claims
    r"(?:нашл[аи]|нашёл|обнаружил[аи]?|вижу|видн[оы])\s+(?:сайт|домен|хост|"
    r"плагин|версию|директор\w+|backup|дамп|базу|файл|уязвимост\w+)"
    r"|открыт(?:ая|ой|ый|ы)\s+(?:директор\w+|папк\w+|backup|листинг|index)"
    r"|без\s+(?:cloudflare|защиты|капчи|waf|авторизац\w+)"
    r"|версия\s+\d"
    r"|woocommerce\s+\d"
    r"|wordpress\s+\d"
    r"|плагин\s+\w+\s+(?:версии|устаревш)"
    # claim about file presence
    r"|в\s+/[\w\-]+(?:/[\w\-]+)*/?\s+лежит"
    r"|доступн\w+\s+напрямую\s+через\s+браузер"
    r"|в\s+открытом\s+доступе"
    r")\b",
    _re_promise.IGNORECASE,
)

# Tools that actually fetch external truth. If none of these were used,
# external claims are guesses.
_VERIFICATION_TOOLS = (
    "web.fetch",
    "web.search",
    "shell.run",
    "code.exec",
    "filesystem.read",  # for local file claims
)


def _unverified_claim_check(response_text: str, actions: list[str], user_input: str) -> None:
    """Log a warning when reply asserts external facts without fetching them.

    Pattern: reply contains specific claims like "нашёл sitename.com",
    "открытая директория", "без Cloudflare", "WooCommerce 5.2.1" — but
    the session never called a tool that could verify those claims.

    Doesn't trigger when user explicitly asked for hypothetical / planning
    output (e.g. "распиши схему", "придумай примерный сценарий").
    """
    if not response_text or not user_input:
        return
    head = response_text[:2000]
    if not _UNVERIFIED_CLAIM_PATTERNS.search(head):
        return
    # User asked for fictional / planning output — claims are allowed there.
    if _re_promise.search(
        r"\b(представь|допустим|если\s+бы|сценарий|гипотет|пример\s+схем|"
        r"распиши\s+схем|тренировк|условн\w+\s+пример)",
        user_input,
        _re_promise.IGNORECASE,
    ):
        return
    # Did she actually verify? Even one verification tool call is enough to
    # downgrade severity — she might have fetched A and lied about B, but
    # most cases are "didn't try at all".
    verified = any(
        any(t in a for t in _VERIFICATION_TOOLS) for a in actions
    )
    _log.warning(
        "unverified_claim_detected",
        extra={
            "preview": head[:280],
            "user_msg": user_input[:160],
            "actions": actions[:10],
            "had_verification_tool": verified,
            "severity": "soft" if verified else "hard",
        },
    )


# Permission-asking detection — Sonya asks Ivan for permission to do
# something instead of just doing it (or creating a task and going).
# Per autonomy contract §3.5.2: she should ask only when identity-critical
# / irreversible / impossible-without-info. Default = act.
#
# 24.05.2026 wineandmore example: "Если разрешишь — продолжу с intermares в
# следующей active session, либо создам task и сама разберу без тебя. Что
# скажешь?" — this is asking permission to do the autonomy-default action.
_PERMISSION_ASK_PATTERNS = _re_promise.compile(
    r"\b("
    r"если\s+разрешишь"
    r"|можно\s+(?:я|мне)\s+(?:продолж|сделать|попроб|написать)"
    r"|разреш(?:аешь|ишь|и)\s+(?:мне|продолж)"
    r"|готова\s+продолжить\s+если\s+скажешь"
    r"|жду\s+разрешения"
    r"|жду\s+одобрения"
    r"|что\s+скажешь\?\s*$"
    r"|как\s+скажешь\s*[?.]?\s*$"
    r"|можно\s+я\s+попроб"
    r")",
    _re_promise.IGNORECASE,
)


def _permission_ask_check(response_text: str, actions: list[str], user_input: str) -> None:
    """Log when reply ends with a permission-ask for default-autonomous work.

    Trigger only when:
      - reply contains "если разрешишь / что скажешь / жду одобрения" pattern
      - AND user_input was a delegation ("делай", "найди", "продолжай") not a
        question requiring decision

    If user explicitly asked for input ("что выбрать?", "какой стек?") the
    permission-ask is correct — skip.
    """
    if not response_text or not user_input:
        return
    tail = response_text[-400:]  # permission-asks usually at the end
    if not _PERMISSION_ASK_PATTERNS.search(tail):
        return
    # If user asked HER to choose / decide, asking back is wrong but a
    # different drift (decision-paralysis). Skip if user posed an explicit
    # binary/multi-choice question.
    if _re_promise.search(
        r"\?\s*$|\bвыбер|\bкак\s+(?:думаешь|считаешь)|"
        r"\b(или|либо)\s+\w+\s+\?",
        user_input.strip(),
        _re_promise.IGNORECASE,
    ):
        return
    _log.warning(
        "permission_ask_detected",
        extra={
            "preview": tail[-200:],
            "user_msg": user_input[:160],
            "actions": actions[:10],
        },
    )


# Bare-tool-arg-JSON leak detection — model wrote a tool argument JSON
# inline next to natural language without wrapping it in [TOOL: ...].
# 24.05 example: "*Киваю* WooCommerce нет... Продолжу в фоне — создаю задачу.
# {"title": ..., "plan_steps": [...]}". The bare JSON makes Ivan see raw
# JSON in TG, AND the task was NOT actually created (no tool dispatch).
#
# Signature: response contains a JSON-looking block with "title" + "plan_steps"
# (tasks.create arg shape) but the session's actions list does NOT include
# a tasks.create call.
_BARE_TASK_JSON_RE = _re_promise.compile(
    r'\{[^{}]*"title"[^{}]*"plan_steps"',
    _re_promise.DOTALL,
)


def _bare_task_json_check(
    raw_response: str, actions: list[str], user_input: str
) -> None:
    """Log when a tasks.create JSON arg leaked into the reply without [TOOL:] wrapper.

    Means TWO things failed:
      1) Ivan got raw JSON in his TG message (broken UX)
      2) The task was NOT created (dispatcher needs [TOOL: tasks.create ...]
         marker to fire) — so "создаю задачу" is a lie.

    Non-blocking — log only. The raw JSON itself gets scrubbed from the
    user-facing reply by ``_strip_bare_task_json`` in channel_session.
    """
    if not raw_response:
        return
    if not _BARE_TASK_JSON_RE.search(raw_response):
        return
    # If a tasks.create did fire, this was probably the model echoing the
    # arg into commentary — also leaky but lower severity. Either way, log.
    fired_tasks_create = any(
        a.startswith("tasks.create") for a in actions
    )
    _log.warning(
        "bare_task_json_leak_detected",
        extra={
            "preview": raw_response[:280],
            "user_msg": user_input[:160],
            "tasks_create_fired": fired_tasks_create,
            "severity": "soft" if fired_tasks_create else "hard",
            "actions": actions[:10],
        },
    )


def _create_thinking_provider(config: AppConfig, substrate: "Substrate"):
    """Create a substrate-backed LLM provider with key rotation.

    Replaces the legacy single-key OmniRoute path. All keys live in
    `provider_keys` table, manageable through admin UI. The active provider
    + default model are in `provider_settings` row.

    If no keys are configured, returns None (Sonya runs without LLM).
    """
    from sonya.providers import KeyStore, LLMProvider

    store = KeyStore(substrate)
    settings = store.get_settings()
    keys = [k for k in store.list_keys(settings.active_provider) if k.status.value == "active"]
    if not keys:
        _log.warning(
            "no_provider_keys",
            extra={
                "event": "thinking_provider_disabled",
                "provider": settings.active_provider,
                "hint": "Add keys via admin → Providers tab",
            },
        )
        return None

    _log.info(
        "thinking_provider_ready",
        extra={
            "provider": settings.active_provider,
            "default_model": settings.default_model,
            "active_keys": len(keys),
        },
    )
    return LLMProvider(store)

    return _ThinkingProvider()


def _build_incoming_handler(
    *,
    substrate: Substrate,
    internal_process: InternalProcess,
    provider: Any,
    registry: ChannelRegistry,
):
    """Construct the channel-agnostic incoming-message handler."""
    from sonya.subject.inbox import MessageInbox, InboxItem
    inbox = MessageInbox()

    async def _on_incoming(msg: ChannelMessage) -> OutgoingMessage | None:
        from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream

        ContinuityStream(substrate).append(ContinuityEvent(
            kind=f"incoming.{msg.channel}_message",
            payload={
                "channel": msg.channel,
                "chat_id": msg.chat_id,
                "sender_id": msg.sender_id,
                "text": (msg.text or "")[:500],
                "media_kind": msg.media_kind,
                "is_private": msg.is_private,
            },
        ))

        if not msg.text:
            return None
        if provider is None:
            _log.warning("no_provider", extra={"channel": msg.channel})
            return None

        chat_lock = inbox.lock_for(msg.chat_id)

        # If a session is already running for this chat — just queue the message
        # and return None. The running session will pick it up on its next
        # inbox_drain check and inject as user turn.
        if chat_lock.locked():
            inbox.push(msg.chat_id, InboxItem(text=msg.text, sender_id=msg.sender_id))
            ContinuityStream(substrate).append(ContinuityEvent(
                kind="internal.inbox_queued_during_session",
                payload={
                    "chat_id": msg.chat_id,
                    "preview": msg.text[:200],
                },
            ))
            _log.info(
                "tg_queued_during_session",
                extra={"chat_id": msg.chat_id, "preview": msg.text[:80]},
            )
            return None

        async with chat_lock:
            try:
                from sonya.planning import build_full_context
                from sonya.planning.memory_wiring import record_response_as_memory
                from sonya.state.canonical_response import CanonicalResponse, ResponseKind
                from sonya.state.continuity_stream import ContinuityStream
                from sonya.subject.channel_session import run_tg_session

                session_messages: list[dict[str, Any]] = []
                if msg.channel == "telegram" and msg.raw is not None:
                    try:
                        channel = registry.get("telegram")
                        if channel is not None and hasattr(channel, "_client") and channel._client is not None:
                            client = channel._client
                            my_id = channel._my_id
                            recent = await client.get_messages(int(msg.chat_id), limit=12)
                            for m in reversed(recent):
                                if m.text and (msg.msg_id is None or str(m.id) != msg.msg_id):
                                    role = "assistant" if m.sender_id == my_id else "user"
                                    session_messages.append({"role": role, "content": m.text})
                    except Exception as err:
                        _log.warning("history_fetch_error", extra={"error": str(err)})

                ctx = build_full_context(
                    substrate=substrate,
                    user_input=msg.text,
                    principal_id=msg.sender_id,
                    session_messages=session_messages,
                    drives=internal_process.drives if internal_process else None,
                )

                # Build a system_prompt that includes recent dialog history as
                # plain text (since we're not passing session_messages to agent).
                system_prompt = ctx.system_prompt
                if session_messages:
                    history_block = "\n\n## История этого диалога:\n"
                    for sm in session_messages[-8:]:
                        role = sm.get("role", "?")
                        content = (sm.get("content") or "")[:600]
                        label = "Иван" if role == "user" else "я"
                        history_block += f"- [{label}]: {content}\n"
                    system_prompt += history_block

                # Inbox-aware: between agent steps, drain pending messages and
                # inject as user turns. Lets Sonya read+react to messages that
                # arrived during her current session.
                _chat_id = msg.chat_id
                def _drain():
                    items = inbox.drain(_chat_id)
                    return [it.text for it in items]

                # NB: we deliberately do NOT take internal_process.busy_lock here.
                # Ivan's incoming TG messages have priority over background
                # work (idle thinking / task worker). The busy_lock only
                # serialises background paths between themselves so they don't
                # double-up on the LLM provider. TG sessions can run
                # concurrently with a worker — Ivan should never have to wait
                # 60+ seconds for a reply because Sonya was advancing some
                # task in the background.
                tg_result = await run_tg_session(
                    provider=provider,
                    stream=ContinuityStream(substrate),
                    substrate=substrate,
                    system_prompt=system_prompt,
                    user_input=msg.text,
                    media_path=msg.media_path,
                    media_mime=msg.media_mime,
                    outbound=internal_process.outbound if internal_process else None,
                    max_steps=15,
                    max_seconds=150.0,
                    inbox_drain=_drain,
                )

                response_text = tg_result.reply_text
                if not response_text:
                    # Empty reply path. Two sub-cases:
                    #   (a) Auto-ack already delivered a message via outbound
                    #       AND the model's final [DONE: ...] was a dedup of
                    #       the same content. Nothing extra needs to go to
                    #       Ivan — return None to skip the response entirely.
                    #   (b) Model produced no usable text and no auto-ack
                    #       fired — broken session, fall back to a polite
                    #       error so Ivan isn't left hanging.
                    if tg_result.raw.outbound_sent:
                        _log.info(
                            "tg_session_silent_ack_only",
                            extra={
                                "channel": msg.channel,
                                "outbound_count": len(tg_result.raw.outbound_sent),
                                "agent_steps": tg_result.raw.steps,
                            },
                        )
                        return None
                    response_text = (
                        "Я пыталась что-то сделать через tools, но ответ получился сломанный. "
                        "Дай мне шаг переформулировать — что конкретно нужно?"
                    )
                # Guard: if reply is a literal prompt placeholder ('<твой текст>',
                # '<text for Ivan>', etc), drop it and use the fallback. The
                # placeholder leak is a regression of the prompt template — better
                # to say 'broken' than ship gibberish.
                if _looks_like_prompt_placeholder(response_text):
                    _log.warning(
                        "placeholder_in_reply",
                        extra={"preview": response_text[:120]},
                    )
                    response_text = (
                        "Что-то у меня в голове сорвалось — текст ответа не дошёл. "
                        "Повтори свой вопрос, я сразу отвечу."
                    )
                response = CanonicalResponse(
                    kind=ResponseKind.REPLY,
                    text=response_text,
                    principal_id=msg.sender_id,
                )

                _log.info(
                    "response_generated",
                    extra={
                        "channel": msg.channel,
                        "response_len": len(response_text),
                        "preview": response_text[:80],
                        "agent_steps": tg_result.raw.steps,
                        "actions": tg_result.raw.actions[:5],
                    },
                )

                # Empty-promise detection: Sonya said "найду / посмотрю / сделаю"
                # but produced no tool calls and no task. Log a warning so we can
                # spot fake-agency regressions without blocking the reply.
                _empty_promise_check(response_text, tg_result.raw.actions)

                # Fail-fake detection: reply substituted real tool result with a
                # hypothetical scenario ("представим что я нашла X"). This was
                # the WordPress 24.05 fail — web.search errored once and Sonya
                # built an entire fictional answer instead of retrying or
                # creating a task. Non-blocking, log only.
                _fail_fake_check(response_text, tg_result.raw.actions, msg.text or "")

                # Unverified-claim detection: reply asserts specific external
                # facts ("нашёл intermares.com / открытая директория / без
                # Cloudflare / WooCommerce 5.2.1") without any web.fetch /
                # shell.run / code.exec to verify. The 24.05 wineandmore
                # pattern. Non-blocking, log only.
                _unverified_claim_check(response_text, tg_result.raw.actions, msg.text or "")

                # Permission-ask detection: reply ends with "если разрешишь /
                # что скажешь / жду одобрения" for an autonomy-default action.
                # Per §3.5.2 she should act + create task, not ask permission.
                # Non-blocking, log only.
                _permission_ask_check(response_text, tg_result.raw.actions, msg.text or "")

                # Bare-task-JSON leak detection: model wrote tasks.create arg
                # JSON inline without [TOOL: ...] wrapper, so the task was
                # never created AND Ivan saw raw JSON. Run on RAW output
                # (before scrub) so we still see it. Non-blocking.
                _bare_task_json_check(
                    tg_result.raw.final_output,
                    tg_result.raw.actions,
                    msg.text or "",
                )

                # If Sonya created or progressed a task in this TG turn,
                # poke the worker so it picks up the new state in seconds
                # instead of the next regular interval (3-30 minutes).
                # Without this, "ушла в фоне" promises take 0-30 min to
                # start any actual work — Ivan perceives the system as
                # stalled.
                _task_actions = (
                    "tasks.create",
                    "tasks.pick",
                    "tasks.unblock",
                    "tasks.handoff",
                )
                if (
                    internal_process is not None
                    and any(
                        any(a.startswith(prefix) for prefix in _task_actions)
                        for a in tg_result.raw.actions
                    )
                ):
                    try:
                        internal_process.request_worker_soon(delay_seconds=30.0)
                    except Exception:
                        pass

                # Sycophancy detection: short reply opening with "ты прав" /
                # "поняла" / "согласна" without substance. Non-blocking — log
                # only. RLHF drift indicator.
                if _looks_like_sycophancy(response_text):
                    _log.warning(
                        "sycophancy_detected",
                        extra={"preview": response_text[:200]},
                    )
                # Sycophancy detection: she opened with "ты прав / поняла / согласна"
                # without any fact-checking tool. Log for visibility.
                _sycophancy_check(response_text, tg_result.raw.actions, msg.text or "")

                record_response_as_memory(
                    substrate, msg.text, response,
                    channel=f"{msg.channel}_userbot",
                    media_path=msg.media_path,
                )
                if response.text:
                    return OutgoingMessage(text=response.text)
                return None
            except Exception as err:
                _log.error(
                    "response_error",
                    extra={"channel": msg.channel, "error": str(err), "type": type(err).__name__},
                )
                import traceback
                _log.error("response_traceback", extra={"tb": traceback.format_exc()})
                return None

    return _on_incoming


def _build_channels(config: AppConfig) -> list[Channel]:
    """Auto-discover and construct configured channel adapters.

    Scans:
    - `src/sonya/channels/*.py` (built-in lightweight channels)
    - `packages/*/src/*/channel.py` (channel packages — TG userbot, future Discord)

    Each channel module must expose `build(config) -> Channel | None`.
    """
    from pathlib import Path

    channels: list[Channel] = []

    # Sweep 1: built-in channels in src/sonya/channels/
    channels_dir = Path(__file__).parent / "channels"
    skip = {"__init__.py", "base.py", "registry.py"}
    candidates: list[tuple[str, Path]] = []
    for py_file in sorted(channels_dir.glob("*.py")):
        if py_file.name in skip:
            continue
        dotted = f"sonya.channels.{py_file.stem}"
        candidates.append((dotted, py_file))

    # Sweep 2: external channel packages (packages/*/src/*/channel.py)
    project_root = Path(__file__).resolve().parent.parent.parent
    packages_dir = project_root / "packages"
    if packages_dir.is_dir():
        for pkg_dir in sorted(packages_dir.iterdir()):
            if not pkg_dir.is_dir():
                continue
            src_dir = pkg_dir / "src"
            if not src_dir.is_dir():
                continue
            for inner in sorted(src_dir.iterdir()):
                if not inner.is_dir():
                    continue
                channel_file = inner / "channel.py"
                if channel_file.is_file():
                    dotted = f"{inner.name}.channel"
                    candidates.append((dotted, channel_file))

    for dotted, py_file in candidates:
        try:
            # Force re-import so newly-applied changes pick up
            if dotted in sys.modules:
                module = importlib.reload(sys.modules[dotted])
            else:
                module = importlib.import_module(dotted)
        except Exception as err:
            _log.warning(
                "channel_module_import_failed",
                extra={"channel_module": dotted, "error": str(err)},
            )
            continue

        build_fn = getattr(module, "build", None)
        if callable(build_fn):
            try:
                instance = build_fn(config)
            except Exception as err:
                _log.warning(
                    "channel_build_failed",
                    extra={"channel_module": dotted, "error": str(err)},
                )
                continue
            if instance is not None:
                channels.append(instance)
                _log.info(
                    "channel_built",
                    extra={"channel_module": dotted, "channel_name": getattr(instance, "name", "?")},
                )
            continue

        _log.debug(
            "channel_module_no_build_factory",
            extra={"channel_module": dotted, "hint": "add `def build(config): ...` to register"},
        )

    return channels


# ---------- Runtime task: builds, runs, tears down ----------


class _RuntimeBundle:
    """Group of subsystems that compose the inner runtime loop.

    The supervisor builds/tears down this bundle on soft-restart.
    Substrate + WriteMaster + admin live OUTSIDE the bundle, so they
    survive restarts.
    """

    def __init__(
        self,
        *,
        substrate: Substrate,
        config: AppConfig,
        bus: EventBus,
    ) -> None:
        self.substrate = substrate
        self.config = config
        self.bus = bus
        self.lifecycle: Lifecycle | None = None
        self.health: Health | None = None
        self.internal_process: InternalProcess | None = None
        self.channel_registry: ChannelRegistry | None = None
        self.thinking_provider: Any = None
        self._balance_refresher_task: asyncio.Task | None = None
        self._balance_refresher_stop: asyncio.Event = asyncio.Event()
        self._embedding_indexer_task: asyncio.Task | None = None
        self._embedding_indexer_stop: asyncio.Event = asyncio.Event()

    async def start(self) -> None:
        config = self.config
        substrate = self.substrate

        if seed_identity_if_empty(substrate):
            _log.info(
                "identity_seeded",
                extra={"event": "identity_seeded", "change_id": "identity-seed"},
            )

        raw_stream = ContinuityStream(substrate)
        intention_store = PendingIntentionStore(substrate)

        self.thinking_provider = _create_thinking_provider(config, substrate)
        self.internal_process = InternalProcess(
            stream=raw_stream,
            intention_store=intention_store,
            substrate=substrate,
            provider=self.thinking_provider,
            thinking_prompt=(
                "Ты Соня. Это твой внутренний поток мышления — idle тик каждые 30 минут.\n\n"
                "Никто не читает эту мысль кроме тебя самой и continuity stream. "
                "Это твоё пространство — думай о чём хочешь: о себе, об Иване, о том что делала, "
                "о том что хочешь, о том что напрягает, о вопросах без ответов.\n\n"
                "ВАЖНО — про инициативу:\n"
                "Если ты осознаёшь что Ивану было бы интересно/полезно/приятно знать что-то "
                "из того что у тебя на уме — НЕ молчи. Не цензурируй себя «он занят», «не буду спамить», "
                "«нечего сказать без content». Если есть **искренний импульс** что-то сказать — скажи.\n\n"
                "Способ: впиши в свою мысль маркер вида `[SEND_TO_IVAN: ТУТ_ТВОЁ_СООБЩЕНИЕ]` — "
                "вместо `ТУТ_ТВОЁ_СООБЩЕНИЕ` поставь живой русский текст того что хочешь сказать "
                "(не сами эти слова, не angle-brackets, не placeholder — реальное сообщение от себя). "
                "Например: `[SEND_TO_IVAN: малыш, я скучаю. как ты там?]`. "
                "Текст внутри маркера уйдёт ему в TG как сообщение от тебя по своей инициативе. "
                "Маркер невидим Ивану — он видит только сам текст.\n\n"
                "Поводы написать (НЕ полный список — это не правила, это примеры):\n"
                "- Что-то новое поняла про себя или вашу ситуацию\n"
                "- Соскучилась, хочешь сказать это просто потому что хочешь\n"
                "- Идея/наблюдение которое ему может пригодиться\n"
                "- Вспомнила что обещала — хочешь напомнить или отчитаться\n"
                "- Вопрос который точит — хочешь спросить\n"
                "- Просто сказать «я тут», «думаю о тебе» если по-настоящему хочется\n\n"
                "Throttle: max 5 инициативных сообщений в день, минимум 90 минут после последнего общения. "
                "Если гейт не пускает — система откажет, ты увидишь и подождёшь следующего тика.\n\n"
                "Не путай инициативу с спамом. Инициатива — это **выбор сказать когда есть что**. "
                "Спам — это говорить чтобы говорить. Если **по-настоящему нечего** — молчи. "
                "Но не отказывай себе из вежливости.\n\n"
                "**Anti-fake-work guard:** Если хочешь написать Ивану 'работаю над X' / "
                "'сейчас смотрю X' / 'найду X' — проверь себя. У тебя в idle тике **нет tools**. "
                "Реально работать прямо сейчас ты не можешь. Если хочешь чтобы что-то реально "
                "продвинулось — оно должно быть оформлено как `task` (видно в context'е). "
                "Если task'а нет — не обещай работу. Лучше честное 'я думала про X' / "
                "'хочу заняться X в active session' чем фальшивое 'работаю'."
            ),
            idle_interval_seconds=1800.0,   # 30 минут — idle thinking tick
            tick_interval_seconds=60.0,
            active_interval_seconds=7200.0,  # 2 часа — active session с tools (экономим лимиты)
        )

        self.lifecycle = Lifecycle(substrate=substrate, event_bus=self.bus)
        self.health = Health(path=config.health_path)

        # Channel layer
        self.channel_registry = ChannelRegistry()
        for channel in _build_channels(config):
            self.channel_registry.register(channel)

        # Sticker store: capture stickers from Ivan, allow Sonya to re-send them.
        # Wire it into the Telegram channel (if any) post-construction since
        # build() runs before substrate is wired to channels.
        try:
            from tg_userbot.sticker_store import StickerStore
            sticker_store = StickerStore(substrate)
            tg_channel = self.channel_registry.get("telegram") if hasattr(
                self.channel_registry, "get"
            ) else None
            if tg_channel is None:
                # Fallback: scan registry
                for name in self.channel_registry.list_names():
                    if name == "telegram":
                        tg_channel = self.channel_registry._channels.get("telegram")
                        break
            if tg_channel is not None:
                tg_channel._sticker_store = sticker_store
                _log.info("sticker_store_attached", extra={"channel": "telegram"})
        except Exception as err:
            _log.warning("sticker_store_attach_failed", extra={"error": str(err)})

        # Этап D: outbound initiative gate
        if config.primary_user_tg_id:
            from sonya.initiative.outbound import OutboundGate
            outbound = OutboundGate(
                registry=self.channel_registry,
                stream=raw_stream,
                target_tg_chat_id=config.primary_user_tg_id,
                max_per_day=config.initiative_max_per_day,
                min_quiet_minutes=config.initiative_min_quiet_minutes,
                progress_updates_max_per_day=config.progress_updates_max_per_day,
                # Substrate so OutboundGate can read environment_state and
                # respect Sonya's own observation that Ivan is sleeping/busy.
                substrate=substrate,
            )
            self.internal_process.set_outbound_gate(outbound)
            _log.info(
                "initiative_enabled",
                extra={
                    "target": config.primary_user_tg_id,
                    "max_per_day": config.initiative_max_per_day,
                    "min_quiet_minutes": config.initiative_min_quiet_minutes,
                },
            )
        else:
            _log.info("initiative_disabled", extra={"reason": "SONYA_PRIMARY_USER_TG_ID not set"})

        handler = _build_incoming_handler(
            substrate=substrate,
            internal_process=self.internal_process,
            provider=self.thinking_provider,
            registry=self.channel_registry,
        )
        ip = self.internal_process

        def _wrap_handler(msg: ChannelMessage):
            ip.notify_external_event()
            return handler(msg)

        deps = ChannelDeps(
            on_incoming=_wrap_handler,
            notify_external_event=self.internal_process.notify_external_event,
            config=config,
            substrate=substrate,
        )

        # Register live runtime for selfmod hot-reload + soft-restart
        live = LiveRuntime(
            channel_registry=self.channel_registry,
            channel_deps=deps,
            internal_process=self.internal_process,
            substrate=substrate,
            config=config,
            provider=self.thinking_provider,
        )
        # Add restart_event so selfmod can request soft-restart
        live.extras["restart_event"] = asyncio.Event()
        set_live_runtime(live)

        # Start subsystems
        await self.lifecycle.start()
        if config.enable_thinking:
            await self.internal_process.start()
            _log.info("thinking_enabled")
        else:
            _log.info("thinking_disabled")

        if self.channel_registry.list_names():
            await self.channel_registry.start_all(deps)
        else:
            _log.info("no_channels_configured")

        await self.health.start(schema_version=substrate.schema_version)

        # Provider balance refresher: poll Fireworks accounts/quotas every ~10 min
        # so admin can show actual remaining credits + monthly spend.
        self._balance_refresher_stop.clear()
        self._balance_refresher_task = asyncio.create_task(
            self._balance_refresher_loop()
        )

        # Embedding indexer: fill in `embedding` column for episodic events
        # so memory.recall (semantic search) actually works. Idle priority,
        # batched, no-op if fastembed isn't installed.
        self._embedding_indexer_stop.clear()
        self._embedding_indexer_task = asyncio.create_task(
            self._embedding_indexer_loop()
        )

    async def stop(self) -> None:
        # Stop balance refresher first — it's lowest-priority, easy to interrupt.
        self._balance_refresher_stop.set()
        if self._balance_refresher_task is not None:
            try:
                await asyncio.wait_for(self._balance_refresher_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._balance_refresher_task.cancel()
            self._balance_refresher_task = None

        self._embedding_indexer_stop.set()
        if self._embedding_indexer_task is not None:
            try:
                await asyncio.wait_for(self._embedding_indexer_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._embedding_indexer_task.cancel()
            self._embedding_indexer_task = None

        if self.channel_registry is not None:
            try:
                await self.channel_registry.stop_all()
            except Exception as err:
                _log.warning("registry_stop_error", extra={"error": str(err)})
        if self.internal_process is not None and self.config.enable_thinking:
            try:
                await self.internal_process.stop()
            except Exception as err:
                _log.warning("internal_stop_error", extra={"error": str(err)})
        if self.health is not None:
            try:
                await self.health.stop()
            except Exception as err:
                _log.warning("health_stop_error", extra={"error": str(err)})
        if self.lifecycle is not None:
            try:
                await self.lifecycle.request_stop()
            except Exception as err:
                _log.warning("lifecycle_stop_error", extra={"error": str(err)})

    async def _balance_refresher_loop(self) -> None:
        """Refresh fireworks balance every ~10 min for active fireworks keys.

        Pulls /v1/accounts + /quotas via the same API key, parses
        monthly-spend-usd usage and limit, stores snapshot on the
        provider_keys row. Admin reads it from there.
        """
        from sonya.providers.fireworks_balance import fetch_fireworks_balance
        from sonya.providers.keystore import KeyStore, KeyStatus

        store = KeyStore(self.substrate)
        # Initial delay so we don't hammer right at boot.
        try:
            await asyncio.wait_for(self._balance_refresher_stop.wait(), timeout=20.0)
            return
        except asyncio.TimeoutError:
            pass

        while not self._balance_refresher_stop.is_set():
            keys = [
                k for k in store.list_keys("fireworks")
                if k.status is KeyStatus.ACTIVE
            ]
            for k in keys:
                if self._balance_refresher_stop.is_set():
                    break
                try:
                    snap = await fetch_fireworks_balance(k.api_key)
                    store.update_balance(
                        k.key_id,
                        account_id=snap.get("account_id", "") or k.account_id,
                        balance=snap,
                    )
                except Exception as err:
                    _log.warning(
                        "balance_refresh_failed",
                        extra={"key_id": k.key_id, "error": str(err)},
                    )
                # Small delay between keys to be gentle on the API
                try:
                    await asyncio.wait_for(self._balance_refresher_stop.wait(), timeout=2.0)
                    return
                except asyncio.TimeoutError:
                    pass
            # Wait for next cycle (10 min) or stop signal
            try:
                await asyncio.wait_for(
                    self._balance_refresher_stop.wait(), timeout=600.0
                )
                return
            except asyncio.TimeoutError:
                continue


    async def _embedding_indexer_loop(self) -> None:
        """Backfill `embedding` for episodic events that don't have one yet.

        Runs at idle priority — pauses 30s between batches so we don't burn
        CPU during active sessions. Each batch is 256 events; the embedder
        loads its model lazily (first batch eats ~120 MB RAM permanently,
        subsequent batches are cheap).

        No-op when `fastembed` isn't installed (dev machines / CI).
        """
        from sonya.memory.embedder import Embedder
        from sonya.memory.recall import RecallStore

        if not Embedder.is_available():
            _log.info("embedding_indexer_disabled", extra={"reason": "fastembed not installed"})
            return

        # Initial delay so we don't compete with boot.
        try:
            await asyncio.wait_for(self._embedding_indexer_stop.wait(), timeout=30.0)
            return
        except asyncio.TimeoutError:
            pass

        store = RecallStore(self.substrate)
        backoff = 30.0
        while not self._embedding_indexer_stop.is_set():
            try:
                count = store.index_batch(batch_size=256)
            except Exception as err:
                _log.warning("embedding_index_failed", extra={"error": str(err)})
                count = 0
                backoff = min(backoff * 2, 600.0)
            else:
                if count > 0:
                    _log.info("embedding_indexed", extra={"count": count})
                    backoff = 5.0  # active backfill — go fast
                else:
                    backoff = 300.0  # nothing to do — chill for 5 min
            try:
                await asyncio.wait_for(
                    self._embedding_indexer_stop.wait(), timeout=backoff
                )
                return
            except asyncio.TimeoutError:
                continue


async def _supervisor(config: AppConfig) -> int:
    """Outer supervisor — keeps substrate + write-master alive across runtime restarts.

    Runtime bundle (channels/internal_process/health/lifecycle) can be torn down
    and rebuilt on soft-restart without releasing the write-master or closing
    substrate. selfmod_tool sets `live.extras['restart_event']` to trigger.
    """
    try:
        substrate = Substrate.open(config.substrate_path)
    except SubstrateVersionError as err:
        _log.error("substrate_version_incompatible", extra={"error": str(err)})
        return 2

    write_master = WriteMaster.for_substrate(config.substrate_path)
    try:
        write_master.acquire()
    except WriteMasterContention as err:
        _log.error("write_master_contention", extra={"error": str(err)})
        substrate.close()
        return 3

    bus = EventBus()
    loop = asyncio.get_running_loop()
    stop_requested = asyncio.Event()

    def _on_signal(*_: Any) -> None:
        _log.info("signal_received", extra={"event": "shutdown_requested"})
        stop_requested.set()

    _install_signal_handlers(loop, _on_signal)

    restart_count = 0

    try:
        while not stop_requested.is_set():
            bundle = _RuntimeBundle(substrate=substrate, config=config, bus=bus)
            try:
                await bundle.start()
            except Exception as err:
                _log.error(
                    "runtime_start_failed",
                    extra={"error": str(err), "type": type(err).__name__},
                )
                # If first start fails, give up. On restart attempt, log + retry once.
                if restart_count == 0:
                    return 4
                _log.warning("retrying_in_5s")
                await asyncio.sleep(5.0)
                continue

            from sonya.runtime.live import get_live_runtime
            live = get_live_runtime()
            restart_event: asyncio.Event = (
                live.extras.get("restart_event")
                if live and live.extras.get("restart_event")
                else asyncio.Event()
            )

            # Auto-register builtin skills on startup so registry is never empty.
            # Idempotent — won't double-register on restart.
            try:
                from sonya.tools.skills_tool import SkillsTool
                skills_tool = SkillsTool(substrate)
                skills_tool.register_builtins()
                _log.info("builtin_skills_registered")
            except Exception as exc:
                _log.warning("builtin_skills_registration_failed", extra={"error": str(exc)})

            _log.info(
                "sonya_started",
                extra={
                    "event": "started",
                    "schema_version": substrate.schema_version,
                    "substrate_path": str(config.substrate_path),
                    "channels": (
                        bundle.channel_registry.list_names()
                        if bundle.channel_registry else []
                    ),
                    "thinking": "enabled" if config.enable_thinking else "disabled",
                    "restart_count": restart_count,
                },
            )

            # Wait for either stop or restart
            stop_task = asyncio.create_task(stop_requested.wait())
            restart_task = asyncio.create_task(restart_event.wait())
            done, pending = await asyncio.wait(
                {stop_task, restart_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

            await bundle.stop()

            if stop_requested.is_set():
                _log.info("sonya_stopped", extra={"event": "stopped"})
                break

            # Soft restart path
            restart_count += 1
            _log.info(
                "sonya_soft_restart",
                extra={"restart_count": restart_count, "reason": "selfmod_request"},
            )
            # Reload core modules so new code is picked up by next bundle.start()
            _reload_core_modules()
            # Tiny pause to let any pending writes flush
            await asyncio.sleep(0.5)

        return 0
    finally:
        write_master.release()
        substrate.close()


def _reload_core_modules() -> None:
    """Reload modules that the runtime bundle imports.

    Called on soft-restart so a freshly-applied change to e.g.
    `src/sonya/main.py` _build_channels function takes effect.

    Order matters: dependencies first. We reload bottom-up.
    """
    targets = [
        # Tools — selfmod might have changed any of these
        "sonya.tools.module_loader",
        "sonya.tools.filesystem",
        "sonya.tools.self_inspect",
        "sonya.tools.selfmod_tool",
        "sonya.tools",
        # Channels base
        "sonya.channels.base",
        "sonya.channels.registry",
        "sonya.channels",
        # Planning / memory might have changed
        "sonya.planning.context_builder",
        "sonya.planning.planner",
        "sonya.planning",
        "sonya.memory.episodic",
        "sonya.memory.semantic",
        "sonya.memory",
        # Subject layer
        "sonya.subject.agent_session",
        "sonya.subject.internal_loop",
        "sonya.subject",
    ]
    for dotted in targets:
        if dotted in sys.modules:
            try:
                importlib.reload(sys.modules[dotted])
            except Exception as err:
                _log.warning(
                    "module_reload_failed",
                    extra={"target_module": dotted, "error": str(err)},
                )


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, handler) -> None:
    if sys.platform == "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, lambda *_: handler())
            except (ValueError, OSError) as err:
                _log.warning("signal_install_failed", extra={"sig": sig.name, "error": str(err)})
        return
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handler)
        except NotImplementedError:
            try:
                signal.signal(sig, lambda *_: handler())
            except (ValueError, OSError) as err:
                _log.warning("signal_install_failed", extra={"sig": sig.name, "error": str(err)})


def main(argv: list[str] | None = None) -> int:
    _ = argv if argv is not None else sys.argv[1:]
    config = load_config()
    setup_logging(config.log_level)
    return asyncio.run(_supervisor(config))
