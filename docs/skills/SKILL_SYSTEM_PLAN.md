# SKILL SYSTEM

**Status:** Active (real, partial)
**Type:** System Plan
**Last reviewed:** 2026-05-28
**Scope:** Skill lifecycle, registry, trust levels, evolution. Что есть в production сейчас и куда идём.
**Depends on:** [SONYA_SYSTEM_CORE.md](../core/SONYA_SYSTEM_CORE.md), [MASTER.md](../MASTER.md)

---

## 1. Базовый принцип

Навык — не просто кусок текста. Это **управляемая единица поведения** с identity, версией, областью применения, trust level, traceability, lifecycle.

Если skill system сводится к prompt snippets — проект теряет один из центральных контуров роста.

## 2. Что есть сейчас (real)

### 2.1 Substrate

`skills` table в substrate (v5+). Поля:
- `skill_id`, `name`, `purpose`, `version`, `status`
- `trust_level` — `core-trusted | trusted | limited | experimental | quarantined`
- `activation_rules_json`, `dependencies_json`
- `allowed_tools_json`, `forbidden_zones_json`
- `tests_json`, `metrics_json`, `trace_tags_json`, `history_json`
- `created_at`

`capability_gaps` table — детектор недостающих способностей (сейчас pattern-based, см. CRUTCH-007).

### 2.2 Builtin skills (3, auto-registered на startup)

- **memory-search** — semantic recall over episodic events
- **identity-check** — verify response stays consistent with identity_record
- **dialog-tone** — match user's last 5 messages tone (formal/casual/role-play)

Регистрация автоматическая в `main.py` при первом старте. После регистрации skills.run может их выполнять.

### 2.3 Skill executor

`src/sonya/skills/` — registry + executor. Соня вызывает через tool `skills.run <skill_id> <input>`. Trust-level check блокирует quarantined. Skill outcome → episodic event ("skill X сработал/не сработал на input Y").

## 3. Skill Lifecycle

```
1. creation       — proposal или manual seed
2. review         — tests + identity check + trust assignment
3. activation     — registry, allowed tools defined
4. observation    — execution traces, metrics
5. evaluation     — usage frequency, success rate, anchor compatibility
6. revision       — improvement proposals (через selfmod pipeline)
7. archive/rollback — если outcome degraded
```

## 4. Trust Levels

Influence на доступ к инструментам, право предлагать изменения, sensitive context access:

- `core-trusted` — built-in, identity-relevant (memory-search, identity-check)
- `trusted` — passed all validation, used in production
- `limited` — restricted scope, не allowed in identity-sensitive paths
- `experimental` — new, monitored heavily
- `quarantined` — known issues, не запускается без explicit override

## 5. Activation rules

- Кто активирует skill (Соня сама / capability gap detector / explicit user)
- В каком контексте допустим
- Какие сигналы нужны для включения
- Какие каналы/инструменты может использовать
- Как логируется исполнение

В текущей реализации — простые JSON правила в `activation_rules_json`. На RWKV — будут native state-level activation.

## 6. Skill Injection User Message

### 6.1 Что это

Механизм перевода повторяющегося пользовательского паттерна в системный артефакт.

### 6.2 Цель

- находить повторяющиеся инструкции
- определять promotable patterns
- превращать их в skill/instruction artifact
- выносить из дорогого повторяющегося текста
- сокращать токены, повышать устойчивость поведения

### 6.3 Текущий статус

**Не реализовано полностью.** Capability gap detector существует (pattern-based), но конвертация gap → skill proposal не автоматическая. Это P2 в [MASTER §6.2](../MASTER.md).

## 7. Real-time Skill Evolution

### 7.1 Что есть

Skill improvement proposals через **selfmod pipeline** — same путь что для кода. Layer 1 syntax / Layer 2 pytest / Layer 3 stub / Layer 4 anchor integrity → apply → 24h watchdog → confirm/revert.

### 7.2 Что нужно

- Capability gap → autoproposal (P2 priority в MASTER)
- Outcome tracking — delta usage / success rate за 7 дней после apply

### 7.3 Что НЕ допускается

Навыки не должны менять себя silently. Любая эволюция skill должна быть:
- traceable
- reviewable
- revertible
- scoped

## 8. Skill Failure Modes

Отслеживаются:
- stale skills (не используются N дней)
- over-triggering (срабатывают чаще чем нужно)
- conflict between skills
- unsafe tool amplification
- silent drift after revisions
- prompt-bloat disguised as skill behavior
- anchor-incompatible skills (Layer 4 ловит на validation)

## 9. Skill Testing

У каждого важного навыка должны быть:
- usage checks
- behavioral checks
- tool safety checks where relevant
- regression checks
- anchor compatibility checks for sensitive skills

В MVP часть может быть rules-based или manual-gated, но **тестовый контур обязан быть**.

## 10. Skill System и личность

Skill system не подменяет identity layer. Навыки — расширения поведения. Identity — ядро самости.

Skill system подчиняется:
- identity constraints
- anchor constraints
- harness rules
- self-modification governance

Конкретно: skill не может ослаблять `things_not_to_betray`. Layer 4 anchor integrity ловит на validate любую попытку.

## 11. Что считается провалом

Skill system провалена если:
- набор prompt snippets без lifecycle
- папка markdown без activation logic
- хаотическое накопление skill-файлов без registry
- самоправка без trust levels and review path
- token-saving tricks без реального behavioral value

## 12. Куда идти дальше

P2 priority в [MASTER §6.2](../MASTER.md):
- Capability gap detector → автоматически создаёт SelfModificationProposal для нового skill
- Active session подхватывает gap → предлагает skill → пишет код → registers через selfmod pipeline
- Skill outcome tracking — delta после 7 дней применения

После Stage 6 (RWKV): skills становятся state-level activations, не SQL records. Но registry + trust + lifecycle переживают.
