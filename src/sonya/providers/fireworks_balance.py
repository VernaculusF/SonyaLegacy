"""Fireworks-specific balance/quota fetcher.

Fireworks doesn't expose a single 'credits remaining' endpoint, but it does
expose:
- GET /v1/accounts          → list of accounts associated with the API key
- GET /v1/accounts/{id}/quotas → all quotas including `monthly-spend-usd`
                                 with current `usage` and `value` (limit)

We pull both, extract the most useful fields, and store as a snapshot on the
provider_keys row. Refreshed periodically (every ~10 min) by a background
loop. Admin and Sonya can view it.

Returned structure (stored as balance_json):
{
    "account_id": "fizikg-mk1l40a6jert",
    "display_name": "Jester",
    "email": "fizikg@list.ru",
    "suspend_state": "UNSUSPENDED",
    "monthly_spend_usd": {"usage": 0.0, "limit": 50.0},
    "serverless_rpm": {"usage": 0, "limit": 6000},
    "rate_limited_models": [...],   // future
    "fetched_at": "2026-...",
    "ok": true,
    "error": "",
}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

_log = logging.getLogger("sonya.providers.fireworks_balance")


_INTERESTING_QUOTAS = {
    "monthly-spend-usd": "monthly_spend_usd",
    "serverless-inference-rpm": "serverless_rpm",
}


async def fetch_fireworks_balance(api_key: str, *, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch account info + quotas. Returns a snapshot dict (always; on error sets `ok=False`)."""
    snap: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ok": False,
        "error": "",
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get("https://api.fireworks.ai/v1/accounts", headers=headers)
            if r.status_code != 200:
                snap["error"] = f"GET /accounts → HTTP {r.status_code}: {r.text[:200]}"
                return snap
            data = r.json()
            accs = data.get("accounts", []) or []
            if not accs:
                snap["error"] = "no accounts associated with this key"
                return snap
            acc = accs[0]
            account_full_name = acc.get("name", "")  # "accounts/<id>"
            account_id = account_full_name.split("/")[-1] if account_full_name else ""
            snap["account_id"] = account_id
            snap["display_name"] = acc.get("displayName", "")
            snap["email"] = acc.get("email", "")
            snap["suspend_state"] = acc.get("suspendState", "")
            snap["account_state"] = acc.get("state", "")
            if not account_id:
                snap["error"] = "could not parse account_id"
                return snap

            r2 = await c.get(
                f"https://api.fireworks.ai/v1/accounts/{account_id}/quotas",
                headers=headers,
            )
            if r2.status_code != 200:
                snap["error"] = f"GET /quotas → HTTP {r2.status_code}: {r2.text[:200]}"
                return snap
            qdata = r2.json()
            for q in qdata.get("quotas", []) or []:
                name = (q.get("name") or "").split("/")[-1]
                if name not in _INTERESTING_QUOTAS:
                    continue
                key = _INTERESTING_QUOTAS[name]
                limit = _safe_num(q.get("value"))
                # API returns max_value too — that's account spending tier ceiling
                max_value = _safe_num(q.get("maxValue"))
                usage = _safe_num(q.get("usage"))
                snap[key] = {
                    "usage": usage,
                    "limit": limit,
                    "max_value": max_value,
                    "remaining": max(0.0, limit - usage) if limit > 0 else None,
                }
            snap["ok"] = True
            return snap
    except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as err:
        snap["error"] = f"network: {type(err).__name__}: {err}"
        return snap
    except Exception as err:
        snap["error"] = f"{type(err).__name__}: {err}"
        return snap


def _safe_num(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0
