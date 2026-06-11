"""Compatibility facade for the v34 SituationalModel.

Legacy callers still use key/value operations. Human/environment observations
are now persisted as sourced, expiring-capable situational assertions rather
than eternal values in ``environment_state``.
"""

from __future__ import annotations

from typing import Any

from sonya.state.situational import SituationalStore
from sonya.state.substrate import Substrate


class EnvironmentStore:
    """Legacy key/value view over Sonya's global situational assertions."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate
        self._situational = SituationalStore(substrate)

    def set(
        self,
        key: str,
        value: str,
        *,
        source: str = "observation",
        updated_by: str = "",
        subject: str = "environment",
        confidence: float = 0.5,
        expires_at: str = "",
    ) -> None:
        key = (key or "").strip()
        if not key:
            raise ValueError("environment key is required")
        if key.startswith("ivan_"):
            subject = "ivan"
        self._situational.assert_fact(
            subject=subject,
            predicate=key,
            value=value,
            source=source,
            source_ref=updated_by,
            confidence=confidence,
            expires_at=expires_at,
        )

    def get(self, key: str) -> dict[str, Any] | None:
        subject = "ivan" if key.startswith("ivan_") else "environment"
        item = self._situational.get_current(subject=subject, predicate=key)
        if item is None:
            return None
        return {
            "key": item.predicate,
            "value": item.value,
            "source": item.source,
            "updated_at": item.observed_at,
            "updated_by": item.source_ref,
            "confidence": item.confidence,
            "expires_at": item.expires_at,
            "subject": item.subject,
        }

    def list_all(self) -> dict[str, dict[str, Any]]:
        current = self._situational.list_current()
        return {
            item.predicate: {
                "value": item.value,
                "source": item.source,
                "updated_at": item.observed_at,
                "updated_by": item.source_ref,
                "confidence": item.confidence,
                "expires_at": item.expires_at,
                "subject": item.subject,
            }
            for item in current
        }

    def clear(self, key: str) -> bool:
        subject = "ivan" if key.startswith("ivan_") else "environment"
        return self._situational.retract(
            subject=subject, predicate=key
        )


__all__ = ["EnvironmentStore"]
