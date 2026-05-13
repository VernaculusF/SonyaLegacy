from __future__ import annotations

import json
from dataclasses import dataclass, field


ALLOWED_ACTION_TYPES = {
    "reply",
    "generate_image",
    "reply_and_generate_image",
    "create_task",
    "reply_and_create_task",
    "ask_clarification",
    "report_limitation",
}


@dataclass(frozen=True, slots=True)
class RuntimeTaskPayload:
    kind: str
    goal: str
    requested_by_principal: str = ""
    origin_channel: str = ""
    origin_chat_id: str = ""
    source_message: str = ""
    context_summary: str = ""
    suggested_steps: tuple[str, ...] = field(default_factory=tuple)
    priority: int = 3
    requires_user_followup: bool = False
    followup_prompt: str = ""


@dataclass(frozen=True, slots=True)
class RuntimeAction:
    type: str
    reply_text: str = ""
    image_prompt: str = ""
    task_payload: RuntimeTaskPayload | None = None


def _parse_json_payload(text: str) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _coerce_task_payload(payload: dict | None) -> RuntimeTaskPayload | None:
    if not isinstance(payload, dict):
        return None
    kind = str(payload.get("kind") or "").strip()
    goal = str(payload.get("goal") or "").strip()
    if not kind or not goal:
        return None
    steps_raw = payload.get("suggested_steps") or []
    steps = tuple(str(item).strip() for item in steps_raw if str(item).strip())
    try:
        priority = int(payload.get("priority", 3))
    except (TypeError, ValueError):
        priority = 3
    return RuntimeTaskPayload(
        kind=kind,
        goal=goal,
        requested_by_principal=str(payload.get("requested_by_principal") or "").strip(),
        origin_channel=str(payload.get("origin_channel") or "").strip(),
        origin_chat_id=str(payload.get("origin_chat_id") or "").strip(),
        source_message=str(payload.get("source_message") or "").strip(),
        context_summary=str(payload.get("context_summary") or "").strip(),
        suggested_steps=steps,
        priority=max(1, min(priority, 5)),
        requires_user_followup=bool(payload.get("requires_user_followup")),
        followup_prompt=str(payload.get("followup_prompt") or "").strip(),
    )


def parse_runtime_action(text: str) -> RuntimeAction | None:
    payload = _parse_json_payload(text)
    if payload is None:
        return None

    reply_text = str(payload.get("reply_text") or "").strip()
    image_prompt = str(payload.get("image_prompt") or "").strip()
    task_payload = _coerce_task_payload(payload.get("task_payload"))
    action_type = str(payload.get("type") or "").strip()

    if action_type not in ALLOWED_ACTION_TYPES:
        if reply_text and image_prompt:
            action_type = "reply_and_generate_image"
        elif image_prompt:
            action_type = "generate_image"
        elif task_payload and reply_text:
            action_type = "reply_and_create_task"
        elif task_payload:
            action_type = "create_task"
        elif reply_text:
            action_type = "reply"

    if action_type not in ALLOWED_ACTION_TYPES:
        return None

    if action_type in {"create_task", "reply_and_create_task"} and task_payload is None:
        return RuntimeAction(
            type="report_limitation",
            reply_text=reply_text or "Я не могу честно заявить о фоновой работе без оформленной задачи.",
        )
    if action_type == "generate_image" and not image_prompt:
        return None
    if action_type == "reply_and_generate_image" and not image_prompt:
        return None
    if action_type in {"reply", "ask_clarification", "report_limitation"} and not reply_text:
        return None

    return RuntimeAction(
        type=action_type,
        reply_text=reply_text,
        image_prompt=image_prompt,
        task_payload=task_payload,
    )
