from __future__ import annotations

from typing import Iterable

from sonya.providers.base import ProviderBackend


class ProviderRegistry:
    """In-process registry of provider backends.

    No enum-literal of provider names; backends are registered at runtime.
    """

    def __init__(self) -> None:
        self._backends: dict[str, ProviderBackend] = {}

    def register(self, name: str, backend: ProviderBackend) -> None:
        if name in self._backends:
            raise ValueError(f"provider {name!r} is already registered")
        self._backends[name] = backend

    def get(self, name: str) -> ProviderBackend:
        if name not in self._backends:
            raise KeyError(name)
        return self._backends[name]

    def list(self) -> list[str]:
        return list(self._backends.keys())

    def find_by_capability(self, *, needs_modes: Iterable[str]) -> list[str]:
        """Return provider names whose capability supports all required input modes."""
        needs = set(needs_modes)
        out: list[str] = []
        for name, backend in self._backends.items():
            cap = backend.capabilities()
            if needs.issubset(set(cap.input_modes)):
                out.append(name)
        return out
