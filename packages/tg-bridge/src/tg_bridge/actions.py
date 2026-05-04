from __future__ import annotations

import json
from dataclasses import dataclass


ALLOWED_ACTION_TYPES = {"reply", "generate_image", "reply_and_generate_image"}


@dataclass(frozen=True, slots=True)
class RuntimeAction:
    type: str
    reply_text: str = ""
    image_prompt: str = ""


def parse_runtime_action(text: str) -> RuntimeAction | None:
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
    if not isinstance(payload, dict):
        return None
    reply_text = str(payload.get("reply_text") or "").strip()
    image_prompt = str(payload.get("image_prompt") or "").strip()
    action_type = str(payload.get("type") or "").strip()
    if action_type not in ALLOWED_ACTION_TYPES:
        if reply_text and image_prompt:
            action_type = "reply_and_generate_image"
        elif image_prompt:
            action_type = "generate_image"
        elif reply_text:
            action_type = "reply"
    if action_type not in ALLOWED_ACTION_TYPES:
        return None
    return RuntimeAction(
        type=action_type,
        reply_text=reply_text,
        image_prompt=image_prompt,
    )

