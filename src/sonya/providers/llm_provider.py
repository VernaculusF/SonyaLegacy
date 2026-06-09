"""Generic OpenAI-compatible LLM provider with substrate-backed key rotation.

Used directly by main._create_thinking_provider — replaces OmniRoute proxy.
Handles Fireworks / OpenRouter / Groq / any /v1/chat/completions endpoint.

Per request:
  1. Acquire eligible key from KeyStore for active_provider
  2. POST to {base_url}/chat/completions
  3. On 429: cooldown the key, retry next
  4. On 5xx: cooldown 30s, retry next (up to 3 keys)
  5. On 401/403: ban the key, retry next
  6. On success: increment success_count
  7. Always: write a row to llm_calls table for audit.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from sonya.providers.keystore import KeyStatus, KeyStore

_log = logging.getLogger("sonya.providers.llm_provider")


class NoKeysAvailable(RuntimeError):
    """All keys exhausted (banned/disabled/cooldown)."""


def _strip_image_content(messages: list[dict]) -> list[dict]:
    """Remove image_url and video_url blocks from multimodal messages.

    When a model doesn't support vision, we retry with text-only content.
    Multimodal messages have content=[{type:text,...},{type:image_url,...}] —
    we keep only text parts. Sonya will see the text placeholder ('[стикер 🫥]')
    instead of the actual image.
    """
    result = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            # Multimodal message — keep only text parts
            text_parts = [p for p in content if isinstance(p, dict) and p.get("type") == "text"]
            if text_parts:
                # Collapse to single string if only one text part
                if len(text_parts) == 1:
                    result.append({**msg, "content": text_parts[0].get("text", "")})
                else:
                    combined = "\n".join(p.get("text", "") for p in text_parts)
                    result.append({**msg, "content": combined})
            else:
                result.append({**msg, "content": "[media — model does not support vision]"})
        else:
            result.append(msg)
    return result


def _has_image_content(messages: list[dict]) -> bool:
    """Check if any message contains image_url or video_url content blocks."""
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") in ("image_url", "video_url"):
                    return True
    return False


def _replace_media_with_description(messages: list[dict], description: str) -> list[dict]:
    """Replace image_url/video_url blocks with a text description from vision model.

    The vision model already described what's in the media. Now we inject that
    description as text so the main (text) model can see it without needing
    vision capabilities.
    """
    result = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            new_parts = []
            has_media = False
            for part in content:
                if isinstance(part, dict) and part.get("type") in ("image_url", "video_url"):
                    has_media = True
                else:
                    new_parts.append(part)
            if has_media:
                # Add the vision description as text
                new_parts.append({"type": "text", "text": f"\n[Визуальное содержимое: {description}]"})
            if len(new_parts) == 1 and new_parts[0].get("type") == "text":
                result.append({**msg, "content": new_parts[0].get("text", "")})
            else:
                result.append({**msg, "content": new_parts})
        else:
            result.append(msg)
    return result


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Per-purpose model hints (2026-06-02: replaces slot-based routing).
#
# Ivan's directive: no "text-fast" / "text-deep" distinctions. All keys are
# "text". Sonya/system chooses the model per purpose. The hint below is the
# *default* model name for each purpose; Sonya can override per-request via
# the ``_model`` kwarg. If a hint model isn't available, the provider
# falls back to its default model (provider_settings.default_model).

_PURPOSE_MODEL_HINT: dict[str, str] = {
    # Interactive, latency-sensitive — use Flash for speed
    "tg_session": "accounts/fireworks/models/deepseek-v4-flash",
    "idle_thinking": "accounts/fireworks/models/deepseek-v4-flash",
    "pre_done_critique": "accounts/fireworks/models/deepseek-v4-flash",
    # Active session / tasks / research — Pro for quality
    "active_session": "accounts/fireworks/models/deepseek-v4-pro",
    "task_worker": "accounts/fireworks/models/deepseek-v4-pro",
    "active_session_deep": "accounts/fireworks/models/deepseek-v4-pro",
    "research": "accounts/fireworks/models/deepseek-v4-pro",
    # Codegen — Pro handles code well
    "selfmod_codegen": "accounts/fireworks/models/deepseek-v4-pro",
    "selfmod_propose": "accounts/fireworks/models/deepseek-v4-pro",
}

_PROVIDER_DEFAULT_BASE_URL: dict[str, str] = {
    "codexsale": "https://codex.sale/v1",
}

_PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    # Conservative default for direct premium provider: cheaper/faster than
    # full GPT-5.4/5.5, still high quality for explicit fallback use.
    "codexsale": "gpt-5.4-mini",
}


def _model_for_purpose(purpose: str) -> str:
    """Return the preferred model for a given purpose.

    Returns "" if no hint — the provider falls back to its default_model.
    """
    return _PURPOSE_MODEL_HINT.get(purpose, "")
    if purpose in _PURPOSE_SLOT_MAP:
        return _PURPOSE_SLOT_MAP[purpose]
    # Codegen-shaped purposes that don't fit the explicit map
    if "code" in purpose.lower() or "_codegen" in purpose.lower() or "selfmod" in purpose.lower():
        return "code"
    return "text"


def _record_call(
    store: KeyStore,
    *,
    key_id: str,
    provider: str,
    model: str,
    purpose: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_ms: int,
    status: str,
    http_status: int,
    error: str,
) -> None:
    """Insert one row into llm_calls. Best-effort, never raises."""
    try:
        store._sub.connection.execute(
            "INSERT INTO llm_calls "
            "(timestamp, key_id, provider, model, purpose, "
            "prompt_tokens, completion_tokens, total_tokens, "
            "latency_ms, status, http_status, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _utc_now_iso(), key_id, provider, model, purpose,
                int(prompt_tokens), int(completion_tokens), int(total_tokens),
                int(latency_ms), status, int(http_status), error[:500],
            ),
        )
        store._sub.connection.commit()
    except Exception:
        pass


class LLMProvider:
    """OpenAI-compatible chat completion provider with key rotation."""

    def __init__(self, store: KeyStore, *, request_timeout: float = 120.0) -> None:
        self._store = store
        self._timeout = request_timeout

    async def complete_text(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> str:
        settings = self._store.get_settings()

        # Vision routing: if messages contain image_url/video_url blocks,
        # use vision model AS EYES ONLY — describe the media, then pass
        # the description to the main (text) model which generates the reply.
        has_images = (
            not kwargs.get("_vision_stripped")
            and _has_image_content(messages)
        )

        if has_images:
            # Step 1: ask vision model to describe the visual content
            description = await self._describe_visual(messages, purpose=kwargs.get("purpose", "unknown"))
            if description:
                # Step 2: replace media blocks with text description, send to main model
                described_msgs = _replace_media_with_description(messages, description)
                return await self.complete_text(
                    described_msgs,
                    **{**kwargs, "_vision_stripped": True},
                )
            else:
                # Vision failed — strip media, proceed text-only
                stripped_msgs = _strip_image_content(messages)
                return await self.complete_text(
                    stripped_msgs,
                    **{**kwargs, "_vision_stripped": True},
                )

        provider = str(kwargs.get("_provider") or settings.active_provider or "").strip() or settings.active_provider
        max_attempts = max(1, kwargs.get("_max_key_attempts", 5))
        purpose = kwargs.get("purpose", "unknown")
        explicit_provider = bool(str(kwargs.get("_provider", "")).strip())

        # Model selection: explicit _model > role-based from provider_models pool > purpose hint > provider default.
        if "_model" in kwargs:
            preferred_model = str(kwargs["_model"])
        else:
            role = str(kwargs.get("role", "auto")).strip()
            preferred_model = ""
            if role and role != "auto":
                pool_models = self._store.list_provider_models(provider=provider, enabled_only=True)
                role_matches = [m for m in pool_models if m.role_preference == role and m.enabled]
                if role_matches:
                    free_matches = [m for m in role_matches if m.is_free]
                    if free_matches:
                        preferred_model = free_matches[0].model_id
                    else:
                        preferred_model = role_matches[0].model_id
            if not preferred_model:
                preferred_model = _model_for_purpose(purpose)

        # Fallback chain: try active_provider first; if no eligible keys
        # there, fall back to other providers in order.
        fallback_chain = [provider]
        if not explicit_provider:
            for fb in ("kr", "fireworks", "openrouter", "codexsale"):
                if fb != provider and fb not in fallback_chain:
                    fallback_chain.append(fb)

        last_err: Exception | None = None

        for attempt in range(max_attempts):
            key = None
            picked_provider = provider
            # 2026-06-02: no slot filtering. All keys are "text".
            # Just pick any eligible key from the chain.
            for prov in fallback_chain:
                key = await self._store.acquire(prov)
                if key is not None:
                    picked_provider = prov
                    if prov != provider and attempt == 0:
                        _log.info(
                            "provider_fallback_acquired",
                            extra={"primary": provider, "fallback": prov, "purpose": purpose},
                        )
                    break

            if key is None:
                if attempt == 0:
                    raise NoKeysAvailable(
                        f"no active keys for provider '{provider}' or any fallback. "
                        f"Add via admin → Providers tab."
                    )
                break

            # Model selection: preferred_model (from purpose hint or explicit
            # _model kwarg) takes priority. Falls back to key.model (if the
            # key has a fixed model like kr/claude-haiku-4.5), then
            # provider_settings.default_model.
            model = preferred_model or key.model or _PROVIDER_DEFAULT_MODEL.get(picked_provider) or settings.default_model
            base_url = key.base_url or _PROVIDER_DEFAULT_BASE_URL.get(picked_provider) or settings.default_base_url
            url = f"{base_url.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key.api_key}",
            }
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 4000),
                "temperature": kwargs.get("temperature", 0.9),
                "stream": False,
            }

            t_start = time.time()
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self._timeout, connect=10.0),
                ) as client:
                    resp = await client.post(url, headers=headers, json=payload)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.ConnectError) as err:
                latency_ms = int((time.time() - t_start) * 1000)
                _log.warning(
                    "key_transient_error",
                    extra={"key_id": key.key_id, "provider": picked_provider, "type": type(err).__name__, "attempt": attempt},
                )
                _record_call(
                    self._store, key_id=key.key_id, provider=picked_provider, model=model,
                    purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    latency_ms=latency_ms, status="error", http_status=0,
                    error=f"{type(err).__name__}: {err}",
                )
                await self._store.report_failure(
                    key.key_id, kind="other", error_message=f"{type(err).__name__}: {err}"
                )
                last_err = err
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            except Exception as err:
                latency_ms = int((time.time() - t_start) * 1000)
                _log.error("key_unexpected_error", extra={"key_id": key.key_id, "type": type(err).__name__})
                _record_call(
                    self._store, key_id=key.key_id, provider=picked_provider, model=model,
                    purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    latency_ms=latency_ms, status="error", http_status=0,
                    error=f"{type(err).__name__}: {err}",
                )
                await self._store.report_failure(key.key_id, kind="other", error_message=str(err))
                last_err = err
                continue

            latency_ms = int((time.time() - t_start) * 1000)

            if resp.status_code in (401, 403):
                _log.warning("key_auth_error", extra={"key_id": key.key_id, "status": resp.status_code, "body": resp.text[:200]})
                _record_call(
                    self._store, key_id=key.key_id, provider=picked_provider, model=model,
                    purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    latency_ms=latency_ms, status="auth", http_status=resp.status_code,
                    error=resp.text[:300],
                )
                await self._store.report_failure(
                    key.key_id, kind="auth_error",
                    error_message=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )
                last_err = RuntimeError(f"auth error from {provider}")
                continue

            if resp.status_code == 429:
                retry_after = self._parse_retry_after(resp)
                _log.warning("key_rate_limited", extra={"key_id": key.key_id, "retry_after": retry_after})
                _record_call(
                    self._store, key_id=key.key_id, provider=picked_provider, model=model,
                    purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    latency_ms=latency_ms, status="rate_limit", http_status=429,
                    error=resp.text[:300],
                )
                await self._store.report_failure(
                    key.key_id, kind="rate_limit",
                    error_message=f"HTTP 429: {resp.text[:200]}",
                    retry_after_seconds=retry_after,
                )
                last_err = RuntimeError("rate limit")
                continue

            if 500 <= resp.status_code < 600:
                _log.warning("key_server_error", extra={"key_id": key.key_id, "status": resp.status_code, "body": resp.text[:200]})
                _record_call(
                    self._store, key_id=key.key_id, provider=picked_provider, model=model,
                    purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    latency_ms=latency_ms, status="server_error", http_status=resp.status_code,
                    error=resp.text[:300],
                )
                await self._store.report_failure(
                    key.key_id, kind="server_error",
                    error_message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
                last_err = RuntimeError(f"upstream {resp.status_code}")
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

            try:
                resp.raise_for_status()
            except Exception as err:
                status = resp.status_code
                if status == 402 or "suspended" in resp.text.lower() or "credits" in resp.text.lower():
                    failure_kind = "auth_error"
                elif status in (400, 404, 412):
                    failure_kind = "config_error"
                else:
                    failure_kind = "other"
                _log.warning("key_http_error", extra={"key_id": key.key_id, "status": status, "kind": failure_kind, "body": resp.text[:200]})

                _record_call(
                    self._store, key_id=key.key_id, provider=picked_provider, model=model,
                    purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    latency_ms=latency_ms, status=failure_kind, http_status=status,
                    error=resp.text[:300],
                )
                await self._store.report_failure(
                    key.key_id, kind=failure_kind,
                    error_message=f"HTTP {status}: {resp.text[:200]}",
                )
                last_err = err
                if failure_kind == "config_error":
                    break
                continue

            text = resp.text.strip()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                first_line = text.split("\n", 1)[0].strip()
                try:
                    data = json.loads(first_line)
                except Exception as err:
                    _log.warning("key_bad_response", extra={"key_id": key.key_id, "preview": text[:200]})
                    _record_call(
                        self._store, key_id=key.key_id, provider=picked_provider, model=model,
                        purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                        latency_ms=latency_ms, status="error", http_status=resp.status_code,
                        error=f"unparseable: {text[:200]}",
                    )
                    await self._store.report_failure(
                        key.key_id, kind="other",
                        error_message=f"unparseable response: {text[:200]}",
                    )
                    last_err = err
                    continue

            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as err:
                _record_call(
                    self._store, key_id=key.key_id, provider=picked_provider, model=model,
                    purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    latency_ms=latency_ms, status="error", http_status=resp.status_code,
                    error=f"bad shape: {json.dumps(data)[:200]}",
                )
                await self._store.report_failure(
                    key.key_id, kind="other",
                    error_message=f"unexpected response shape: {json.dumps(data)[:200]}",
                )
                last_err = err
                continue

            usage = data.get("usage") or {}
            pt = int(usage.get("prompt_tokens", 0) or 0)
            ct = int(usage.get("completion_tokens", 0) or 0)
            tt = int(usage.get("total_tokens", pt + ct) or (pt + ct))
            _record_call(
                self._store, key_id=key.key_id, provider=picked_provider, model=model,
                purpose=purpose, prompt_tokens=pt, completion_tokens=ct, total_tokens=tt,
                latency_ms=latency_ms, status="ok", http_status=resp.status_code,
                error="",
            )
            await self._store.report_success(key.key_id)
            return content

        if last_err is not None:
            raise last_err
        raise NoKeysAvailable(f"all {max_attempts} key attempts exhausted for provider '{provider}'")

    def _parse_retry_after(self, resp: httpx.Response) -> int:
        """Try to extract retry-after seconds from headers / body."""
        ra = resp.headers.get("retry-after")
        if ra:
            try:
                return int(float(ra))
            except Exception:
                pass
        try:
            body = resp.json()
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(err, dict):
                v = err.get("retry_after") or err.get("retry-after")
                if v:
                    return int(float(v))
        except Exception:
            pass
        return 60

    async def _describe_visual(self, messages: list[dict[str, Any]], purpose: str = "vision") -> str | None:
        """Use vision model as eyes only — extract visual description.

        Sends ONLY the media content + a short "describe" prompt to the vision
        model. Returns a text description, or None on failure.
        This keeps the vision model out of personality/response generation.
        """
        # Extract the multimodal content blocks from messages
        media_blocks = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") in ("image_url", "video_url"):
                        media_blocks.append(part)

        if not media_blocks:
            return None

        # Build a minimal vision request — no personality, no memory
        vision_content: list[dict] = [
            {"type": "text", "text": "Опиши что изображено/происходит на этом медиа. Кратко, 1-3 предложения. Только описание, без комментариев."},
        ] + media_blocks

        vision_messages = [
            {"role": "user", "content": vision_content},
        ]

        # Acquire vision key
        key = await self._store.acquire_by_slot("vision")
        if key is None:
            _log.info("vision_no_keys_fallback")
            return None

        model = key.model or "google/gemma-3-27b-it"
        base_url = key.base_url or "https://openrouter.ai/api/v1"
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key.api_key}",
        }
        payload = {
            "model": model,
            "messages": vision_messages,
            "max_tokens": 300,
            "temperature": 0.3,
            "stream": False,
        }

        t_start = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
            ) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except Exception as err:
            _log.warning("vision_describe_error", extra={"error": str(err)})
            await self._store.report_failure(key.key_id, kind="other", error_message=str(err))
            return None

        latency_ms = int((time.time() - t_start) * 1000)

        if resp.status_code != 200:
            _log.warning("vision_describe_http_error", extra={
                "status": resp.status_code, "body": resp.text[:200], "key_id": key.key_id
            })
            _record_call(
                self._store, key_id=key.key_id, provider=key.provider, model=model,
                purpose="vision_describe", prompt_tokens=0, completion_tokens=0, total_tokens=0,
                latency_ms=latency_ms, status="error", http_status=resp.status_code,
                error=resp.text[:300],
            )
            await self._store.report_failure(
                key.key_id, kind="other",
                error_message=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )
            return None

        try:
            data = resp.json()
            description = data["choices"][0]["message"]["content"]
        except Exception:
            return None

        usage = data.get("usage") or {}
        _record_call(
            self._store, key_id=key.key_id, provider=key.provider, model=model,
            purpose="vision_describe", prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
            latency_ms=latency_ms, status="ok", http_status=200, error="",
        )
        await self._store.report_success(key.key_id)
        _log.info("vision_described", extra={"len": len(description), "latency_ms": latency_ms})
        return description.strip() if description else None
