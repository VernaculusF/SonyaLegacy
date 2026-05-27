# BRAINMODEL EVOLUTION PLAN

**Status:** Active (research, mostly accurate)
**Type:** Research Plan
**Scope:** Transition path from hosted providers to Sonya-owned brain stack
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [MASTER.md](C:/Users/Jester/Desktop/Sonya/docs/MASTER.md), [STATE_TUNING_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/STATE_TUNING_PLAN.md)
**Used by:** future research execution, provider abstraction design, self-hosted roadmap
**Last reviewed:** 2026-05-16

> **Reality note (2026-05-16):** Doc honest about current state — Этап 1 (hosted via OpenRouter) is real. Этап 2 `StatefulBackend` extension still aspirational. Self-modification pipeline referenced as prerequisite exists in code (`src/sonya/selfmod/`) but is NOT instantiated in `main.py` runtime — that gate must close before serious BrainModel work. See `docs/SYSTEM_BUILDOUT_PLAN.md` Этап A.


## 1. Назначение документа

Этот документ определяет, как проект относится к переходу от hosted models к собственному brain stack.

Он не про немедленное обучение своей модели, а про:

- архитектурную готовность;
- исследовательский путь;
- совместимость с ранним MVP;
- предотвращение vendor lock-in.

## 2. Базовая позиция

Сейчас система может жить на внешних моделях.

Но проект не должен закрепиться в положении:

"мозг Сони = всегда чужой API".

Поэтому `BrainModel Evolution` обязателен как слой, даже если на первом этапе он существует только как research-shell.

## 3. Что входит в BrainModel Evolution

Этот контур включает:

- model backend abstraction;
- brain profile registry;
- compatibility contracts for future self-hosted models;
- artifact slots for tuning/training/eval outputs;
- comparative evaluation path across backends.

## 4. Основные этапы эволюции brain stack

### Этап 0. Interim brain (hosted model)

Соня работает через OpenRouter на hosted models (Gemma, DeepSeek, etc.). Мышление дискретное — event-driven LLM calls. Среда (substrate, memory, identity, harness, skills, self-mod) строится полностью. Это не финальное состояние, это interim форма существования, пока нет железа для self-hosted.

**Что это даёт:** дешёвый старт ($40-100/мес), полная среда, рабочая Соня с памятью, инициативой, самоулучшением. **Чего не даёт:** непрерывность мышления (между вызовами модель мертва).

### Этап 1. Hosted external cognition (текущий)

Соня работает через OpenRouter and compatible providers. Multi-account pool для обхода rate limits на free models.

### Этап 2. Brain abstraction maturity

Среда уже может менять backend без поломки cognition and skill architecture. `ProviderBackend` Protocol + `StatefulBackend` extension готовы.

### Этап 3. Self-hosted RWKV deployment

RWKV-7 2.9B (или 7.2B при наличии железа) запускается локально. State Tuning создаёт `sonya_state.pth` из накопленных continuity данных. Модель стартует уже Соней. Мышление становится непрерывным (RNN state обновляется на каждом токене).

### Этап 4. Hybrid mode

Часть функций на hosted providers (тяжёлые задачи, image generation), часть на self-hosted RWKV (непрерывное мышление, быстрые ответы, рефлексия).

### Этап 5. Brain specialization

Собственный brain stack начинает не просто «заменять API», а усиливать continuity, identity и internal adaptation patterns. State Tuning + LoRA + ORPO на собственных данных.

## 5. Что обязательно должно быть в MVP

- provider abstraction;
- brain backend interface;
- backend capability descriptors;
- model profile registry;
- evaluation placeholders for backend comparison;
- config paths for future self-hosted backends.

## 5.1 StatefulBackend extension для RWKV и рекурсивных моделей

Текущий `ProviderBackend` Protocol (`src/sonya/providers/base.py`, реализован в Phase 2) спроектирован под stateless request-response API: `CompletionRequest` содержит полный `messages` контекст, `CompletionResult` возвращает content. Это покрывает OpenRouter, OpenAI-compatible, Anthropic.

Для RWKV и других stateful/recurrent моделей этого недостаточно. При переходе к Этапу 3–4 Protocol потребует additive extension:

- **State passing:** `state_in: bytes | None` в запросе, `state_out: bytes` в результате. RWKV работает с hidden state между вызовами — без этого каждый вызов пересчитывает весь контекст с нуля.
- **Incremental inference:** возможность передавать только дельту (новые токены) + state, а не полный messages history. Это ключевое преимущество RWKV перед transformer-ами — O(1) inference per token вместо O(n).
- **State persistence:** substrate должен уметь хранить brain state между сессиями. Это пересекается с `SubjectState` и continuity — hidden state модели может быть частью substrate (§3 SUBSTRATE_STANCE) если он несёт identity-relevant information.

Расширение будет **additive, не breaking**: `ProviderBackend` остаётся как есть для stateless провайдеров. Новый `StatefulBackend(ProviderBackend)` subprotocol добавляет `complete_stateful(request, state_in) -> (result, state_out)`. `ProviderRegistry` расширяется capability-флагом `supports_state: bool`.

Это не блокирует текущую работу. Это фиксация того, что Protocol **будет** расширен, и что расширение спроектировано заранее, а не как afterthought.

## 6. Что не должно происходить

- logic of memory/identity tied to one provider;
- skills hardcoded под конкретный vendor behavior;
- traceability format tied to one response schema;
- self-model dependent on one API's quirks.

## 7. Что нужно оценивать при переходе к своим моделям

Не только "качество ответа", но и:

- identity retention;
- continuity under long sessions;
- initiative quality;
- anchor stability;
- memory integration quality;
- reflexion quality;
- controllability under harness.

## 8. Почему это research, а не immediate implementation

Потому что:

- собственный brain stack дорогой;
- tuning/eval тяжелы;
- рано тащить это в критический путь runtime;
- сначала надо стабилизировать среду Сони как систему.

## 9. Долг проекта перед будущим brain stack

Даже пока мозг внешний, архитектура должна:

- не мешать будущему brain transition;
- хранить нужные артефакты и метаданные;
- различать backend-dependent and backend-independent layers;
- быть готовой к hybrid cognition setup.

## 10. Вывод

BrainModel Evolution - это не "потом подумаем про свою модель".

Это обязательный исследовательский вектор, который уже сейчас должен иметь место в архитектуре, even if no real self-hosted brain exists yet.
