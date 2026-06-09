from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sonya.providers.keystore import KeyStore, ProviderModel


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


@dataclass(frozen=True)
class PickPolicy:
    """Soft policy for orchestration, not a hard routing rule.

    Sonya uses this to bias the picker toward models that fit the role.
    The picker may still override based on historical success / availability.
    """

    role: str = "auto"
    # auto | planner | executor | reviewer | cleanup | research | composer | vision | transcribe
    prefer_free: bool = True
    prefer_low_latency: bool = True
    allow_premium: bool = True
    min_context_need: str = "auto"
    # auto | small | medium | large


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
    # Also add providers from provider_models pool
    for pm in store.list_provider_models(enabled_only=True):
        out.add(pm.provider)
    return out


def _db_model_profiles(store: KeyStore) -> list[ModelProfile]:
    """Load provider_models from DB and convert to ModelProfile list."""
    profiles: list[ModelProfile] = []
    for pm in store.list_provider_models(enabled_only=True):
        if not pm.text_loop_ok:
            continue
        strengths = pm.strengths()
        strength_keys: list[str] = []
        if pm.context_length >= 500000:
            strength_keys.append("large_context")
        if pm.latency_tier in ("very_fast", "fast"):
            strength_keys.append("general_fast")
        if pm.latency_tier in ("very_fast",):
            strength_keys.append("fastest")
        if pm.latency_tier in ("slow", "very_slow"):
            strength_keys.append("reasoning")
        if "text" not in pm.modalities():
            continue
        for k, v in strengths.items():
            if v >= 0.7 and k not in strength_keys:
                strength_keys.append(k)
        if not strength_keys:
            strength_keys.append("general_reasoning")
        profiles.append(ModelProfile(
            provider=pm.provider,
            model=pm.model_id,
            label=pm.model_name,
            strengths=tuple(strength_keys),
            latency=pm.latency_tier,
            premium=not bool(pm.is_free),
            text_loop_ok=True,
        ))
    return profiles


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


def _role_traits(role: str) -> set[str]:
    role = (role or "auto").strip().lower()
    mapping = {
        "planner": {"research", "hard_reasoning", "large_context", "critical_review"},
        "research": {"research", "large_context", "general_reasoning"},
        "reviewer": {"critical_review", "code_review", "analysis"},
        "cleanup": {"cleanup", "summary", "general_fast"},
        "executor": {"coding", "tools", "general_fast"},
        "composer": {"writing", "creative", "general_reasoning"},
        "vision": {"vision_planning", "ui_ux"},
        "transcribe": {"transcribe"},
    }
    return mapping.get(role, set())


def infer_role(task: str) -> str:
    """Infer a soft orchestration role from the task text.

    This is what lets Sonya decide:
      - planner/researcher for decomposition and architecture
      - executor for implementation
      - reviewer for verification
      - cleanup for polish/repair

    It is intentionally soft: the picker may still override.
    """
    text = (task or "").lower()
    if any(k in text for k in ("plan", "design", "architecture", "decompose", "break down", "spec")):
        return "planner"
    if any(k in text for k in ("review", "audit", "verify", "test", "check", "validate")):
        return "reviewer"
    if any(k in text for k in ("research", "investigate", "compare", "find", "search")):
        return "research"
    if any(k in text for k in ("cleanup", "fix", "refactor", "polish", "format", "simplify")):
        return "cleanup"
    if any(k in text for k in ("write", "implement", "build", "create", "code", "generate", "make")):
        return "executor"
    if any(k in text for k in ("voice", "audio", "transcribe")):
        return "transcribe"
    if any(k in text for k in ("image", "screenshot", "visual", "ui", "ux")):
        return "vision"
    return "auto"


def _cost_bias(profile: ModelProfile, policy: PickPolicy, traits: set[str]) -> int:
    """Prefer small/fast models for execution-like work; stronger models for planning.

    This is deliberately a soft bias, not a hard rule. The historical success
    map can override it when a cheap model proves consistently better.
    """
    score = 0
    role = policy.role.lower().strip()
    if role in ("executor", "cleanup"):
        if profile.latency == "very_fast":
            score += 4
        elif profile.latency == "fast":
            score += 2
        elif profile.latency == "slow":
            score -= 3
        if not profile.premium:
            score += 2
    elif role in ("planner", "research", "reviewer"):
        if profile.latency == "slow":
            score += 3
        elif profile.latency == "medium":
            score += 2
        if profile.premium:
            score += 1
    elif role in ("composer", "vision", "transcribe"):
        if profile.latency in ("fast", "very_fast"):
            score += 2
    else:
        # Auto: mildly prefer cheaper models unless task clearly needs depth.
        if "general_fast" in traits:
            if profile.latency == "very_fast":
                score += 3
            elif profile.latency == "fast":
                score += 2
        else:
            if profile.latency == "slow":
                score += 1
    return score


def pick_subagent_model(
    task: str,
    store: KeyStore,
    *,
    requested_provider: str = "",
    requested_model: str = "",
    substrate: Any = None,
    policy: PickPolicy | None = None,
) -> PickResult:
    requested_provider = (requested_provider or "").strip()
    requested_model = (requested_model or "").strip()

    if requested_model and not requested_provider:
        requested_provider = _infer_provider_from_model(requested_model)

    if requested_provider and requested_model:
        return PickResult(requested_provider, requested_model, "explicit provider+model", auto_selected=False)

    policy = policy or PickPolicy()
    traits = _task_traits(task) | _role_traits(policy.role)
    available = _available_providers(store)
    if not available:
        settings = store.get_settings()
        return PickResult(settings.active_provider, settings.default_model, "fallback to active provider (no eligible key scan result)")

    free_available = any(p in available for p in ("openrouter", "fireworks"))
    premium_needed = bool({"critical_review", "hard_reasoning", "large_context"} & traits)
    prefer_free = policy.prefer_free and free_available and not premium_needed and policy.allow_premium

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
        chosen = max(candidates, key=lambda p: (
            _score(p, traits, prefer_free=False, exp_bonus=exp_map.get((p.provider, p.model), 0))
            + _cost_bias(p, policy, traits)
        ))
        return PickResult(chosen.provider, chosen.model, f"auto-picked within explicit provider {requested_provider} from traits={sorted(traits) or ['default']}")

    candidates = [p for p in _PROFILES if p.provider in available and p.text_loop_ok]
    if not candidates:
        settings = store.get_settings()
        return PickResult(settings.active_provider, settings.default_model, "fallback to active provider (no catalog candidate available)")

    chosen = max(candidates, key=lambda p: (
        _score(p, traits, prefer_free=prefer_free, exp_bonus=exp_map.get((p.provider, p.model), 0))
        + _cost_bias(p, policy, traits)
    ))
    return PickResult(
        chosen.provider,
        chosen.model,
        f"auto-picked {chosen.label} from traits={sorted(traits) or ['default']}, role={policy.role}, prefer_free={prefer_free}",
    )


def list_known_profiles() -> Iterable[ModelProfile]:
    return _PROFILES
