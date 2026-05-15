from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderSecret:
    """Wrapper that prevents accidental leak of secret values via repr/str/log."""

    _value: str

    def __init__(self, value: str) -> None:
        object.__setattr__(self, "_value", value)

    def get_secret_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "ProviderSecret('***')"

    def __str__(self) -> str:
        return "***"


def load_provider_secret(provider_name: str) -> ProviderSecret | None:
    """Read SONYA_<PROVIDER>_API_KEY from env. None if unset."""
    var = f"SONYA_{provider_name.upper()}_API_KEY"
    raw = os.environ.get(var)
    if not raw:
        return None
    return ProviderSecret(raw)
