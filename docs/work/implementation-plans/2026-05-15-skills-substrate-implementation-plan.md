# Skills Substrate & Capability Gap Detection Implementation Plan

**Status:** Active
**Type:** Work Doc
**Scope:** Skill registry with trust levels, capability gap detection, skill proposals through self-mod pipeline, skill injection from user messages. Substrate v5.
**Depends on:** [ROADMAP.md §11](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md), [SKILL_SYSTEM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md), [SELF_REWRITE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md), [SONYA_SYSTEM_CORE.md §7.8-§7.10](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
**Used by:** Phase 5 implementation sessions
**Last reviewed:** 2026-05-15

## 1. Goal

После Phase 5 у Сони есть **skill system** и **базовое самоулучшение**:

- `SkillRegistry` — persistent registry с CRUD, trust levels, activation rules;
- `CapabilityGap` detection — Соня замечает, что ей не хватает функции X;
- Gap → `SelfModificationProposal` — через pipeline из Phase 4;
- Skill Injection — extract promotable patterns из continuity, manual approval → registry.

## 2. Reference Check

### 2.1 OpenClaw
Structured skill approach из `memory_system/lessons/` — берём структурно.

### 2.2 Hermes
Skill — brain. Activation — brain. Execution через tool runtime — Phase 7+.

### 2.3 OmniAgent
Отвергаем `skill_evolution.py` 53KB single-file. Мелкие модули + self-mod pipeline.

## 3. Task List

### Task 1: Substrate v5 + Skill dataclass + SkillRegistry
- Create: `src/sonya/skills/__init__.py`, `src/sonya/skills/skill.py`, `src/sonya/skills/trust.py`, `src/sonya/skills/registry.py`, `tests/sonya/test_skill_registry.py`
- Modify: schema.sql, migrations.py, substrate.py
- Substrate v5: tables `skills`, `capability_gaps`
- `TrustLevel` enum: core_trusted, trusted, limited, experimental, quarantined
- `Skill` frozen dataclass with 14 fields from SKILL_SYSTEM_PLAN §4
- `SkillRegistry`: register, get, list_active, activate, deactivate, persistent

### Task 2: Activation policy
- Create: `src/sonya/skills/activation.py`, `tests/sonya/test_skill_activation.py`
- Rules-based: quarantined skills cannot activate; trust_level check against AuthorityPolicy scope
- Stub for ML matching

### Task 3: Capability gap detection
- Create: `src/sonya/skills/gap_detector.py`, `tests/sonya/test_gap_detector.py`
- Reads recent continuity events, looks for `internal.cognitive_tick` with triggers containing failed patterns
- Creates `CapabilityGap` objects in substrate
- Bridge: gap → SelfModificationProposal via selfmod.ProposalStore

### Task 4: Skill injection from user message
- Create: `src/sonya/skills/injection.py`, `tests/sonya/test_skill_injection.py`
- Extract promotable patterns (simple keyword rules)
- Create candidate skill, requires manual approval
- After approval → promoted to registry

### Task 5: Layer boundary + closure
- Extend AST test for skills/
- Update GLOBAL_PROJECT_CHECKLIST, ROADMAP, DRIFT_REVIEW, archive plan
