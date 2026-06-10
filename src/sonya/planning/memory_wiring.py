from __future__ import annotations

from sonya.memory.episodic import EpisodicMemory
from sonya.state.canonical_response import CanonicalResponse
from sonya.state.substrate import Substrate


def _compute_phash(media_path: str | None) -> str:
    """Compute perceptual hash for an image file. Returns hex string or ''."""
    if not media_path:
        return ""
    try:
        import imagehash
        from PIL import Image
        img = Image.open(media_path)
        h = imagehash.phash(img)
        return str(h)
    except Exception:
        return ""


def record_response_as_memory(
    substrate: Substrate,
    user_input: str,
    response: CanonicalResponse,
    channel: str = "telegram",
    media_path: str | None = None,
    project_id: str = "",
) -> None:
    episodic = EpisodicMemory(substrate)
    phash = _compute_phash(media_path) if media_path else ""

    if user_input:
        episodic.record(
            event_type="dialogue_event",
            raw_content=user_input,
            normalized_summary=f"Иван написал: {user_input[:100]}",
            source="user",
            channel=channel,
            actor=response.principal_id or "ivan",
            importance_score=0.5,
            record_type="dialogue_event",
            scope="main_chat",
            project_id=project_id,
            retention_policy="medium",
        )
        if phash:
            try:
                substrate.connection.execute(
                    "UPDATE episodic_events SET media_phash = ? "
                    "WHERE event_id = (SELECT event_id FROM episodic_events "
                    "ORDER BY rowid DESC LIMIT 1)",
                    (phash,),
                )
                substrate.connection.commit()
            except Exception:
                pass

    if response.text:
        episodic.record(
            event_type="dialogue_event",
            raw_content=response.text,
            normalized_summary=f"Соня ответила: {response.text[:100]}",
            source="sonya",
            channel=channel,
            actor="sonya",
            importance_score=0.6,
            record_type="dialogue_event",
            scope="main_chat",
            project_id=project_id,
            retention_policy="medium",
        )


def record_initiative_as_memory(
    substrate: Substrate,
    text: str,
    *,
    reason: str = "idle_thought",
    channel: str = "telegram_initiative",
    project_id: str = "",
) -> None:
    episodic = EpisodicMemory(substrate)
    if not text or not text.strip():
        return
    episodic.record(
        event_type="initiative_event",
        raw_content=text,
        normalized_summary=f"Я написала первой ({reason}): {text[:100]}",
        source="sonya",
        channel=channel,
        actor="sonya",
        importance_score=0.7,
        record_type="initiative_event",
        scope="main_chat",
        project_id=project_id,
        retention_policy="medium",
    )


def record_session_outcome_as_memory(
    substrate: Substrate,
    *,
    purpose: str,
    steps: int,
    actions: list[str],
    summary: str,
    channel: str = "internal_session",
    importance_score: float = 0.6,
    project_id: str = "",
) -> None:
    if steps <= 0 and not summary:
        return
    episodic = EpisodicMemory(substrate)
    actions_brief = " · ".join(a.split(" ", 1)[0] if " " in a else a for a in actions[:6])
    norm = f"{purpose}: {steps} шагов · {actions_brief or 'без tools'}"
    if summary and summary != "(see prior agent_step)" and summary != "no explicit finish":
        norm = f"{norm} :: {summary[:120]}"
    raw = (
        f"[{purpose} — {steps} steps]\n"
        f"Actions: {', '.join(actions[:8]) or '(none)'}\n"
        f"Result: {summary[:1500]}"
    )
    episodic.record(
        event_type="session_outcome",
        raw_content=raw,
        normalized_summary=norm[:240],
        source="sonya",
        channel=channel,
        actor="sonya",
        importance_score=importance_score,
        record_type="session_outcome",
        scope="global",
        project_id=project_id,
        retention_policy="medium",
    )
