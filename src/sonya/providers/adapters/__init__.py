from __future__ import annotations

from sonya.providers.adapters.base import (
    AdapterCapabilities,
    AdapterHealth,
    AdapterInferenceRequest,
    AdapterInferenceResult,
    DiscoveredModel,
    ProviderAdapter,
    QuotaSnapshot,
)
from sonya.providers.adapters.google_native import GoogleNativeAdapter
from sonya.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from sonya.providers.adapters.factory import build_lifecycle_adapter

__all__ = [
    "AdapterCapabilities",
    "AdapterHealth",
    "AdapterInferenceRequest",
    "AdapterInferenceResult",
    "DiscoveredModel",
    "GoogleNativeAdapter",
    "OpenAICompatibleAdapter",
    "build_lifecycle_adapter",
    "ProviderAdapter",
    "QuotaSnapshot",
]
