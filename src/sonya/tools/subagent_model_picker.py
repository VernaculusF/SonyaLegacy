from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sonya.providers.keystore import KeyStore


@dataclass(frozen=True)
class ModelProfile:
    provider: str
    model: str
    label: str
    strengths: tuple[str, ...]
    latency: str
    premium: bool = False
    text_loop_ok: bool = True


@dataclass(frozen=True)
class PickResult:
    provider: str
    model: str
    reason: str
    auto_selected: bool = True


_PROFILES: tuple[ModelProfile, ...] = (
    ModelProfile("openrouter", "openrouter/owl-alpha", "Owl Alpha", ("research", "math", "large_context", "general_reasoning"), "slow"),
    ModelProfile("openrouter", "poolside/laguna-m.1:free", "Laguna M.1", ("coding", "code_review", "tools"), "medium"),
    ModelProfile("openrouter", "moonshotai/kimi-k2.6:free", "Kimi K2.6", ("coding", "agentic", "ui_ux", "vision_planning"), "medium"),
    ModelProfile("openrouter", "nousresearch/hermes-3-llama-3.1-405b:free", "Hermes 3 405B", ("uncensored", "creative", "open_ended", "reasoning"), "slow"),
    ModelProfile("openrouter", "google/gemma-4-31b-it:free", "Gemma 4 31B", ("summary", "classification", "general_fast"), "fast"),
    ModelProfile("openrouter", "google/gemma-4-26b-a4b-it:free", "Gemma 4 26B A4B", ("summary", "classification", "cleanup", "fastest"), "very_fast"),
    ModelProfile("codexsale", "gpt-5.5", "GPT-5.5", ("critical_review", "research", "hard_reasoning"), "medium", premium=True),
    ModelProfile("codexsale", "gpt-5.4", "GPT-5.4", ("coding", "hard_reasoning", "analysis"), "medium", premium=True),
    ModelProfile("codexsale", "gpt-5.4-mini", "GPT-5.4 Mini", ("summary", "cleanup", "general_fast"), "fast", premium=True),
    ModelProfile("codexsale", "gpt-image-2", "GPT Image 2", ("image_generation",), "n/a", premium=True, text_loop_ok=False),
    ModelProfile("codexsale", "gpt-4o-transcribe", "GPT-4o Transcribe", ("transcribe",), "n/a", premium=True, text_loop_ok=False),
    ModelProfile("fireworks", "accounts/fireworks/models/deepseek-v4-pro", "DeepSeek V4 Pro", ("coding", "general_reasoning"), "medium"),
    ModelProfile("fireworks", "accounts/fireworks/models/deepseek-v4-flash", "DeepSeek V4 Flash", ("summary", "general_fast"), "fast"),
    ModelProfile("kr", "kr/claude-sonnet-4.5", "Claude Sonnet 4.5", ("coding", "writing", "analysis"), "medium", premium=True),
    ModelProfile("kr", "kr/claude-haiku-4.5", "Claude Haiku 4.5", ("summary", "cleanup", "general_fast"), "fast", premium=True),
)


def _task_traits(task: str) -> set[str]:
    text = (task or "").lower()
    traits: set[str] = set()

    if any(k in text for k in ("refactor", "debug", "bug", "traceback", "stacktrace", "exception", "failing test", "regression", "code review", "module", "function", "class", "repo", "codebase", "file", "python", "rust", "typescript", "javascript")):
        traits.add("coding")
    if any(k in text for k in ("review", "audit", "critical", "production", "high risk", "careful", "thorough")):
        traits.add("critical_review")
    if any(k in text for k in ("research", "investigate", "osint", "survey", "find out", "compare", "analyze", "analyse")):
        traits.add("research")
    if any(k in text for k in ("math", "equation", "proof", "logic", "reasoning", "algorithm")):
        traits.add("math")
    if any(k in text for k in ("summarize", "summary", "extract", "classify", "parse", "clean", "cleanup", "normalize", "quick pass")):
        traits.add("summary")
    if any(k in text for k in ("clean", "cleanup", "normalize", "sanitize", "reformat")):
        traits.add("cleanup")
    if any(k in text for k in ("fast", "quick", "small", "short", "brief")):
        traits.add("general_fast")
    if any(k in text for k in ("long context", "huge", "entire repo", "many files", "whole codebase", "1m", "million tokens")):
        traits.add("large_context")
    if any(k in text for k in ("ui", "ux", "layout", "design", "component", "frontend", "screenshot")):
        traits.add("ui_ux")
    if any(k in text for k in ("uncensored", "creative", "roleplay", "persona", "open ended")):
        traits.add("uncensored")
    if any(k in text for k in ("transcribe", "audio", "voice note", "speech to text")):
        traits.add("transcribe")
    if any(k in text for k in ("generate image", "draw", "render", "image generation", "poster", "art")):
        traits.add("image_generation")
    return traits


def _available_providers(store: KeyStore) -> set[str]:
    out: set[str] = set()
    for key in store.list_keys():
        if key.is_eligible():
            out.add(key.provider)
    return out


def _profiles_for_provider(provider: str) -> list[ModelProfile]:
    return [p for p in _PROFILES if p.provider == provider and p.text_loop_ok]


def _infer_provider_from_model(model: str) -> str:
    for profile in _PROFILES:
        if profile.model == model:
            return profile.provider
    if model.startswith("accounts/fireworks/models/"):
        return "fireworks"
    if model.startswith("kr/"):
        return "kr"
    return ""


def is_text_loop_model(model: str, provider: str = "") -> bool:
    provider = (provider or "").strip()
    for profile in _PROFILES:
        if profile.model != model:
            continue
        if provider and profile.provider != provider:
            continue
        return profile.text_loop_ok
    return True


def _score(profile: ModelProfile, traits: set[str], *, prefer_free: bool, exp_bonus: int = 0) -> int:
    score = 0
    for strength in profile.strengths:
        if strength in traits:
            score += 5
    if "coding" in traits and "coding" in profile.strengths:
        score += 3
    if "research" in traits and "research" in profile.strengths:
        score += 3
    if "math" in traits and "math" in profile.strengths:
        score += 3
    if "ui_ux" in traits and "ui_ux" in profile.strengths:
        score += 3
    if "large_context" in traits and "large_context" in profile.strengths:
        score += 4
    if "critical_review" in traits and "critical_review" in profile.strengths:
        score += 4
    if "uncensored" in traits and "uncensored" in profile.strengths:
        score += 4
    if "cleanup" in traits and "cleanup" in profile.strengths:
        score += 3
    if "cleanup" in traits and "fastest" in profile.strengths:
        score += 2

    if not traits and "general_fast" in profile.strengths:
        score += 2

    if prefer_free and profile.premium:
        score -= 4
    if not prefer_free and profile.premium:
        score += 2

    if profile.latency == "very_fast" and "general_fast" in traits:
        score += 2
    if profile.latency == "very_fast" and "summary" in traits:
        score += 2
    if profile.latency == "fast" and "summary" in traits:
        score += 1
    if profile.latency == "slow" and "general_fast" in traits:
        score -= 3

    score += exp_bonus
    return score


def pick_subagent_model(
    task: str,
    store: KeyStore,
    *,
    requested_provider: str = "",
    requested_model: str = "",
    substrate: Any = None,
) -> PickResult:
    requested_provider = (requested_provider or "").strip()
    requested_model = (requested_model or "").strip()

    if requested_model and not requested_provider:
        requested_provider = _infer_provider_from_model(requested_model)

    if requested_provider and requested_model:
        return PickResult(requested_provider, requested_model, "explicit provider+model", auto_selected=False)

    traits = _task_traits(task)
    available = _available_providers(store)
    if not available:
        settings = store.get_settings()
        return PickResult(settings.active_provider, settings.default_model, "fallback to active provider (no eligible key scan result)")

    free_available = any(p in available for p in ("openrouter", "fireworks"))
    premium_needed = bool({"critical_review", "hard_reasoning"} & traits)
    prefer_free = free_available and not premium_needed

    exp_map: dict[tuple[str, str], int] = {}
    if substrate is not None:
        try:
            from sonya.memory.tool_experience import ToolExperience
            tx = ToolExperience(substrate)
            for stat in tx.model_stats(since_hours=168):
                key = (stat["provider"], stat["model"])
                bonus = 0
                if stat["total"] >= 3:
                    bonus += int(stat["rate"] * 6) - 3
                    if stat["errors"] > stat["success"]:
                        bonus -= 5
                    avg_lat = stat["avg_latency_ms"]
                    if avg_lat > 15000:
                        bonus -= 2
                exp_map[key] = bonus
        except Exception:
            pass

    if requested_provider:
        candidates = _profiles_for_provider(requested_provider)
        if not candidates:
            settings = store.get_settings()
            return PickResult(requested_provider, settings.default_model, f"provider {requested_provider} has no known profile; using provider default")
        chosen = max(candidates, key=lambda p: _score(p, traits, prefer_free=False, exp_bonus=exp_map.get((p.provider, p.model), 0)))
        return PickResult(chosen.provider, chosen.model, f"auto-picked within explicit provider {requested_provider} from traits={sorted(traits) or ['default']}")

    candidates = [p for p in _PROFILES if p.provider in available and p.text_loop_ok]
    if not candidates:
        settings = store.get_settings()
        return PickResult(settings.active_provider, settings.default_model, "fallback to active provider (no catalog candidate available)")

    chosen = max(candidates, key=lambda p: _score(p, traits, prefer_free=prefer_free, exp_bonus=exp_map.get((p.provider, p.model), 0)))
    return PickResult(
        chosen.provider,
        chosen.model,
        f"auto-picked {chosen.label} from traits={sorted(traits) or ['default']}, prefer_free={prefer_free}",
    )


def list_known_profiles() -> Iterable[ModelProfile]:
    return _PROFILES
