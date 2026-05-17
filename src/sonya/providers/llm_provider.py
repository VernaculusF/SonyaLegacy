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
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from sonya.providers.keystore import KeyStatus, KeyStore

_log = logging.getLogger("sonya.providers.llm_provider")


class NoKeysAvailable(RuntimeError):
    """All keys exhausted (banned/disabled/cooldown)."""


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

        last_err: Exception | None = None

        for attempt in range(max_attempts):
            key = await self._store.acquire(provider)
            if key is None:
                # No eligible key — wait briefly in case a cooldown is about to expire
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
                "max_tokens": kwargs.get("max_tokens", 1500),
                "temperature": kwargs.get("temperature", 0.9),
                "stream": False,
            }

            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self._timeout, connect=10.0),
                ) as client:
                    resp = await client.post(url, headers=headers, json=payload)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.ConnectError) as err:
                _log.warning(
                    "key_transient_error",
                    extra={"key_id": key.key_id, "provider": provider, "type": type(err).__name__, "attempt": attempt},
                )
                await self._store.report_failure(
                    key.key_id, kind="other", error_message=f"{type(err).__name__}: {err}"
                )
                last_err = err
                # Brief sleep before next key
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            except Exception as err:
                _log.error("key_unexpected_error", extra={"key_id": key.key_id, "type": type(err).__name__})
                await self._store.report_failure(key.key_id, kind="other", error_message=str(err))
                last_err = err
                continue

            if resp.status_code in (401, 403):
                _log.warning("key_auth_error", extra={"key_id": key.key_id, "status": resp.status_code, "body": resp.text[:200]})
                await self._store.report_failure(
                    key.key_id, kind="auth_error",
                    error_message=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )
                last_err = RuntimeError(f"auth error from {provider}")
                continue

            if resp.status_code == 429:
                retry_after = self._parse_retry_after(resp)
                _log.warning("key_rate_limited", extra={"key_id": key.key_id, "retry_after": retry_after})
                await self._store.report_failure(
                    key.key_id, kind="rate_limit",
                    error_message=f"HTTP 429: {resp.text[:200]}",
                    retry_after_seconds=retry_after,
                )
                last_err = RuntimeError("rate limit")
                continue

            if 500 <= resp.status_code < 600:
                _log.warning("key_server_error", extra={"key_id": key.key_id, "status": resp.status_code, "body": resp.text[:200]})
                await self._store.report_failure(
                    key.key_id, kind="server_error",
                    error_message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
                last_err = RuntimeError(f"upstream {resp.status_code}")
                # Small delay before next attempt
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

            try:
                resp.raise_for_status()
            except Exception as err:
                _log.warning("key_http_error", extra={"key_id": key.key_id, "status": resp.status_code, "body": resp.text[:200]})
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
                    await self._store.report_failure(
                        key.key_id, kind="other",
                        error_message=f"unparseable response: {text[:200]}",
                    )
                    last_err = err
                    continue

            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as err:
                await self._store.report_failure(
                    key.key_id, kind="other",
                    error_message=f"unexpected response shape: {json.dumps(data)[:200]}",
                )
                last_err = err
                continue

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
        # Some providers return JSON like {"error":{"retry_after":60}}
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
