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
import typing

import httpx

from sonya.providers.keystore import KeyStatus, KeyStore, ProviderKey

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


_PURPOSE_MODEL_HINT: dict[str, str] = {}

_PROVIDER_DEFAULT_BASE_URL: dict[str, str] = {
    "codexsale": "https://codex.sale/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
}

_PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    # Conservative default for direct premium provider: cheaper/faster than
    # full GPT-5.4/5.5, still high quality for explicit fallback use.
    "codexsale": "gpt-5.4-mini",
}


def _model_for_purpose(purpose: str, settings: Any) -> str:
    """Return model based on purpose from settings."""
    if "vision" in purpose:
        return settings.vision_model or settings.default_model
    if purpose in ("fast_text", "active_session", "task_worker_fast"):
        return settings.fast_model or settings.default_model
    if purpose in ("deep_text", "self_mod", "task_worker_deep", "planning"):
        return settings.deep_model or settings.default_model
    return settings.default_model


def _provider_fallback_chain(store: KeyStore, primary_provider: str, *, explicit_provider: bool) -> list[str]:
    primary_provider = (primary_provider or "").strip()
    if explicit_provider:
        return [primary_provider] if primary_provider else []

    chain: list[str] = []
    if primary_provider:
        chain.append(primary_provider)

    for model in store.list_available_provider_models():
        if model.provider not in chain:
            chain.append(model.provider)

    for key in sorted(store.list_keys(), key=lambda item: (item.priority, item.provider, item.name)):
        if key.is_eligible() and key.provider not in chain:
            chain.append(key.provider)

    return chain


def _pick_vision_model(store: KeyStore):
    candidates = []
    for model in store.list_available_provider_models():
        modalities = {str(item).lower() for item in model.modalities()}
        if "text" not in modalities:
            continue
        if not ({"image", "vision", "video"} & modalities):
            continue
        candidates.append(model)
    if not candidates:
        return None
    candidates.sort(key=lambda m: (
        0 if m.is_free else 1,
        0 if m.latency_tier in ("very_fast", "fast") else 1,
        -int(m.context_length or 0),
        m.provider,
        m.model_id,
    ))
    return candidates[0]


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


def _resolve_key_secret(store: KeyStore, key: ProviderKey) -> str:
    """Resolve encrypted account credentials before legacy plaintext keys."""
    account = store.get_provider_account(key.key_id)
    if account is not None and account.secret_ref.startswith("provider-secret:"):
        return store.resolve_account_secret(account.account_id).get_secret_value()
    return key.api_key


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

        provider = str(kwargs.get("_provider") or "").strip()
        max_attempts = max(1, kwargs.get("_max_key_attempts", 20))
        purpose = kwargs.get("purpose", "unknown")
        explicit_provider = bool(provider)

        # Model selection: explicit _model > role-based from provider_models pool > purpose hint > provider default.
        if "_model" in kwargs:
            preferred_model = str(kwargs["_model"])
        else:
            role = str(kwargs.get("role", "auto")).strip()
            preferred_model = ""
            if role and role != "auto":
                pool_models = self._store.list_available_provider_models(provider)
                role_matches = [m for m in pool_models if m.role_preference == role and m.enabled]
                if role_matches:
                    free_matches = [m for m in role_matches if m.is_free]
                    if free_matches:
                        preferred_model = free_matches[0].model_id
                    else:
                        preferred_model = role_matches[0].model_id
            if not preferred_model:
                preferred_model = _model_for_purpose(purpose, settings)

        fallback_chain = _provider_fallback_chain(self._store, provider, explicit_provider=explicit_provider)

        last_err: Exception | None = None

        for attempt in range(max_attempts):
            key = None
            picked_provider = provider
            # 2026-06-02: no slot filtering. All keys are "text".
            # If a concrete model is selected, pick only accounts that offer it.
            for prov in fallback_chain:
                key = (
                    await self._store.acquire_for_model(preferred_model, prov)
                    if preferred_model else
                    await self._store.acquire(prov)
                )
                if key is not None:
                    data_confidentiality = kwargs.get("data_confidentiality", "public")
                    account = self._store.get_provider_account(key.key_id)
                    if account is not None:
                        if data_confidentiality == "secret" and account.confidentiality_level != "secret":
                            _log.warning(f"Key {key.key_id} rejected due to confidentiality constraints (needs secret)")
                            key = None
                            continue
                        if data_confidentiality == "internal" and account.confidentiality_level not in ("internal", "secret"):
                            _log.warning(f"Key {key.key_id} rejected due to confidentiality constraints (needs internal/secret)")
                            key = None
                            continue

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
                "Authorization": f"Bearer {_resolve_key_secret(self._store, key)}",
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
            except asyncio.CancelledError:
                raise
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

    
    async def stream_text(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> typing.AsyncIterator[str]:
        """Stream provider-native text deltas."""
        settings = self._store.get_settings()

        # Vision routing is bypassed for streaming since describing visuals is non-streaming.
        has_images = (
            not kwargs.get("_vision_stripped")
            and _has_image_content(messages)
        )
        if has_images:
            # Fall back to synchronous complete_text and yield its result as a single chunk
            full_text = await self.complete_text(messages, **kwargs)
            yield full_text
            return

        provider = str(kwargs.get("_provider") or "").strip()
        max_attempts = max(1, kwargs.get("_max_key_attempts", 20))
        purpose = kwargs.get("purpose", "unknown")
        explicit_provider = bool(provider)

        if "_model" in kwargs:
            preferred_model = str(kwargs["_model"])
        else:
            role = str(kwargs.get("role", "auto")).strip()
            preferred_model = ""
            if role and role != "auto":
                pool_models = self._store.list_available_provider_models(provider)
                role_matches = [m for m in pool_models if m.role_preference == role and m.enabled]
                if role_matches:
                    free_matches = [m for m in role_matches if m.is_free]
                    if free_matches:
                        preferred_model = free_matches[0].model_id
                    else:
                        preferred_model = role_matches[0].model_id
            if not preferred_model:
                preferred_model = _model_for_purpose(purpose, settings)

        fallback_chain = _provider_fallback_chain(self._store, provider, explicit_provider=explicit_provider)

        last_err: Exception | None = None

        import json
        import httpx
        import asyncio
        import time

        for attempt in range(max_attempts):
            key = None
            picked_provider = provider
            for prov in fallback_chain:
                key = (
                    await self._store.acquire_for_model(preferred_model, prov)
                    if preferred_model else
                    await self._store.acquire(prov)
                )
                if key is not None:
                    data_confidentiality = kwargs.get("data_confidentiality", "public")
                    account = self._store.get_provider_account(key.key_id)
                    if account is not None:
                        if data_confidentiality == "secret" and account.confidentiality_level != "secret":
                            _log.warning(f"Key {key.key_id} rejected due to confidentiality constraints (needs secret)")
                            key = None
                            continue
                        if data_confidentiality == "internal" and account.confidentiality_level not in ("internal", "secret"):
                            _log.warning(f"Key {key.key_id} rejected due to confidentiality constraints (needs internal/secret)")
                            key = None
                            continue

                    picked_provider = prov
                    if prov != provider and attempt == 0:
                        _log.info(
                            "provider_fallback_acquired_stream",
                            extra={"primary": provider, "fallback": prov, "purpose": purpose},
                        )
                    break

            if key is None:
                if attempt == 0:
                    raise NoKeysAvailable(
                        f"no active keys for provider '{provider}' or any fallback. "
                        f"Add via admin -> Providers tab."
                    )
                break

            model = preferred_model or key.model or _PROVIDER_DEFAULT_MODEL.get(picked_provider) or settings.default_model
            base_url = key.base_url or _PROVIDER_DEFAULT_BASE_URL.get(picked_provider) or settings.default_base_url
            url = f"{base_url.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_resolve_key_secret(self._store, key)}",
            }
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 4000),
                "temperature": kwargs.get("temperature", 0.9),
                "stream": True,
            }

            t_start = time.time()
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self._timeout, connect=10.0),
                ) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as resp:
                        latency_ms = int((time.time() - t_start) * 1000)
                        
                        if resp.status_code in (401, 403):
                            await resp.aread()
                            _log.warning("key_auth_error_stream", extra={"key_id": key.key_id, "status": resp.status_code, "body": resp.text[:200]})
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
                            await resp.aread()
                            retry_after = self._parse_retry_after(resp)
                            _log.warning("key_rate_limited_stream", extra={"key_id": key.key_id, "retry_after": retry_after})
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
                            await resp.aread()
                            _log.warning("key_server_error_stream", extra={"key_id": key.key_id, "status": resp.status_code, "body": resp.text[:200]})
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
                            await resp.aread()
                            status = resp.status_code
                            if status == 402 or "suspended" in resp.text.lower() or "credits" in resp.text.lower():
                                failure_kind = "auth_error"
                            elif status in (400, 404, 412):
                                failure_kind = "config_error"
                            else:
                                failure_kind = "other"
                            _log.warning("key_http_error_stream", extra={"key_id": key.key_id, "status": status, "kind": failure_kind, "body": resp.text[:200]})

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
                        
                        # Process SSE stream
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices", [])
                                if not choices:
                                    continue
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                pass
                            
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.ConnectError) as err:
                latency_ms = int((time.time() - t_start) * 1000)
                _log.warning(
                    "key_transient_error_stream",
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
            except asyncio.CancelledError:
                raise
            except Exception as err:
                latency_ms = int((time.time() - t_start) * 1000)
                _log.error("key_unexpected_error_stream", extra={"key_id": key.key_id, "type": type(err).__name__})
                _record_call(
                    self._store, key_id=key.key_id, provider=picked_provider, model=model,
                    purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    latency_ms=latency_ms, status="error", http_status=0,
                    error=f"{type(err).__name__}: {err}",
                )
                await self._store.report_failure(key.key_id, kind="other", error_message=str(err))
                last_err = err
                continue

            # Stream finished successfully
            _record_call(
                self._store, key_id=key.key_id, provider=picked_provider, model=model,
                purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                latency_ms=int((time.time() - t_start) * 1000), status="ok", http_status=200,
                error="",
            )
            await self._store.report_success(key.key_id)
            return

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

        # Acquire a first-class provider/account offering with visual input.
        # Legacy `slot=vision` is only a compatibility fallback; provider-pool
        # runtime stores capabilities on provider_models/modalities instead.
        vision_model = _pick_vision_model(self._store)
        key = (
            await self._store.acquire_for_model(vision_model.provider, vision_model.model_id)
            if vision_model is not None else None
        )
        if key is None:
            key = await self._store.acquire_by_slot("vision")
        if key is None:
            _log.info("vision_no_keys_fallback")
            return None

        model = vision_model.model_id if vision_model is not None else (key.model or "google/gemma-3-27b-it")
        base_url = key.base_url or (vision_model.base_url if vision_model is not None else "") or "https://openrouter.ai/api/v1"
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_resolve_key_secret(self._store, key)}",
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
