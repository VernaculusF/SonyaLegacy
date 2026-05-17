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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        provider = settings.active_provider
        max_attempts = max(1, kwargs.get("_max_key_attempts", 5))
        purpose = kwargs.get("purpose", "unknown")

        last_err: Exception | None = None

        for attempt in range(max_attempts):
            key = await self._store.acquire(provider)
            if key is None:
                if attempt == 0:
                    raise NoKeysAvailable(
                        f"no active keys for provider '{provider}'. "
                        f"Add via admin → Providers tab."
                    )
                break

            model = key.model or settings.default_model
            base_url = key.base_url or settings.default_base_url
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
                    extra={"key_id": key.key_id, "provider": provider, "type": type(err).__name__, "attempt": attempt},
                )
                _record_call(
                    self._store, key_id=key.key_id, provider=provider, model=model,
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
                    self._store, key_id=key.key_id, provider=provider, model=model,
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
                    self._store, key_id=key.key_id, provider=provider, model=model,
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
                    self._store, key_id=key.key_id, provider=provider, model=model,
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
                    self._store, key_id=key.key_id, provider=provider, model=model,
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
                _log.warning("key_http_error", extra={"key_id": key.key_id, "status": resp.status_code, "body": resp.text[:200]})
                _record_call(
                    self._store, key_id=key.key_id, provider=provider, model=model,
                    purpose=purpose, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                    latency_ms=latency_ms, status="error", http_status=resp.status_code,
                    error=resp.text[:300],
                )
                await self._store.report_failure(
                    key.key_id, kind="other",
                    error_message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
                last_err = err
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
                        self._store, key_id=key.key_id, provider=provider, model=model,
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
                    self._store, key_id=key.key_id, provider=provider, model=model,
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
                self._store, key_id=key.key_id, provider=provider, model=model,
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
