# ГЛОБАЛЬНЫЙ ЧЕКЛИСТ ПРОЕКТА

**Status:** Active
**Type:** Core
**Scope:** Полный проектный чеклист для всей системы Sonya в рамках исходного замысла
**Depends on:** [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md), [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md)
**Used by:** контроль roadmap, архитектурный аудит, implementation review, drift control, milestone review
**Last reviewed:** 2026-05-02

## Как читать этот файл

Это не sprint todo.

Это полная карта реального состояния проекта.

Обозначения:

- ✅ реально существует на нужном сейчас уровне
- 🟡 существует частично, нестабильно или только как emergency-реализация
- ⬜ не построено

Если что-то существует только как идея в документации, это не ✅.

---

## 1. Направление проекта и governance

- ✅ Идентичность проекта зафиксирована в [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
- ✅ Позиция по субъектности и сознанию зафиксирована в [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md)
- ✅ Корневая карта документации существует
- ✅ Корневой глобальный чеклист существует
- ✅ Правила документации существуют
- ⬜ Каждое крупное изменение кода обновляет truth-доки при смене scope
- ⬜ Каждое крупное изменение кода обновляет этот чеклист при смене реальности
- ⬜ Drift review реально проводится, а не обещается
- ⬜ Мёртвые доки реально убираются, а не копятся
- ⬜ Исходный план декомпозирован без потери смысла

## 2. Репозиторий и структура

- ✅ У Sonya есть свой корень репозитория
- ✅ `docs/` отделён от package code
- ✅ `docs/work/` существует как слой активной рабочей кухни
- ✅ Telegram bridge вынесен за пределы `.openclaw`
- ⬜ Корневой пакет `src/sonya/` существует
- ⬜ Packaging strategy репозитория стабилизирована
- ⬜ Общие config conventions определены
- ⬜ Secret handling conventions определены
- ⬜ Repo onboarding файл для новых сессий существует
- ⬜ Commit/branch hygiene кодифицированы

## 3. Целостность документации

- ✅ У каждого живого документа есть внятная роль
- ✅ Локальные дублирующие index-доки схлопнуты
- ✅ Work-доки отделены от долгоживущей истины
- ✅ Слои `core`, `architecture`, `cognition`, `skills`, `research`, `work` выражены явно
- ⬜ Все cross-reference пути актуальны
- ⬜ Исторические work-доки помечены как active / stale / archive
- ⬜ В доках не осталось старых невалидных путей
- ⬜ Нет конкурирующих дублирующих определений
- ⬜ У каждой крупной подсистемы есть один governing doc
- ⬜ Documentation review входит в completion criteria

## 4. Фаза 0: анализ референсов

- ✅ Общий reference-анализ существует
- ✅ Анализ OpenClaw существует
- ✅ Анализ Hermes существует
- ✅ Анализ OmniAgent существует
- ⬜ У каждого нового implementation slice есть явная проверка против reference-фазы
- ⬜ Зафиксировано, что именно заимствуется из OpenClaw как operational truth
- ⬜ Зафиксировано, что именно понимается как orchestration role в духе Hermes
- ⬜ Зафиксировано, какие shortcut-решения из OmniAgent отвергнуты
- ⬜ Фаза анализа учитывается как обязательная ранняя стадия, а не как старая бумага
- ⬜ Post-analysis discipline реально соблюдается в новых подпланах

## 5. Runtime shell

- ⬜ Пакет `sonya-core` существует
- ⬜ Runtime process model реализован чисто
- ⬜ Runtime bootstrap pipeline реализован
- ⬜ Runtime config loading реализован
- ⬜ Runtime lifecycle management существует
- ⬜ Runtime health status interface существует
- ⬜ Runtime graceful shutdown существует
- ⬜ Runtime restart semantics определены и проверены
- ⬜ Runtime internal state model выражен явно
- ⬜ Runtime subsystem registration существует

## 6. Provider и model layer

- 🟡 Основная текстовая модель и image model разведены в bridge-коде
- 🟡 Config-driven выбор моделей существует в bridge
- ⬜ Provider abstraction существует вне текущего bridge-path
- ⬜ Provider configuration validation существует
- ⬜ Provider capability matrix существует
- ⬜ Cost policy по capability существует
- ⬜ Retry policy по provider path существует
- ⬜ Timeout policy по provider path существует
- ⬜ Model fallback policy существует
- ⬜ Provider audit logging существует

## 7. Text inference path

- 🟡 Текстовый completion path работает через текущий bridge
- ⬜ Text path существует как общая runtime capability
- ⬜ Structured response policy существует
- ⬜ Reasoning/thinking mode policy существует
- ⬜ Streaming text support реализован там, где нужен
- ⬜ Guardrails против malformed model output существуют
- ⬜ Language-handling policy выражена явно
- ⬜ Persona adherence evaluation существует
- ⬜ Tone drift detection существует
- ⬜ Refusal/avoidance behavior сделан намеренно, а не случайно

## 8. Vision path

- 🟡 Vision по фото работает в Telegram bridge
- 🟡 Vision по стикерам работает в Telegram bridge
- 🟡 Vision по image-document работает в Telegram bridge
- 🟡 Video ingestion path существует в bridge
- ⬜ Vision существует как общая runtime capability
- ⬜ Vision media normalization обобщён вне Telegram
- ⬜ Vision prompt policy существует
- ⬜ Vision-specific eval cases существуют
- ⬜ Multi-image reasoning path существует
- ⬜ Large-media handling policy существует

## 9. Image generation path

- 🟡 Отдельный image model path существует
- 🟡 JSON и stream parsing для image response существуют
- 🟡 Telegram delivery картинок работает
- 🟡 Action planner умеет триггерить image generation
- ⬜ Image generation существует как общая runtime capability
- ⬜ Image editing path существует
- ⬜ Aspect ratio configuration path существует
- ⬜ Negative prompt / style policy существует, если понадобится
- ⬜ Image-generation eval fixtures существуют
- ⬜ Image-generation cost policy существует

## 10. Telegram bridge

- ✅ Bridge code extracted into repo package
- ✅ Пакет переименован в `tg-bridge`
- ✅ `.openclaw` запускает repo entrypoint
- ✅ Health-check существует
- 🟡 Живой bridge снова operational
- ⬜ Text round-trip smoke заново прогнан после последних фиксов
- ⬜ Photo round-trip smoke заново прогнан после последних фиксов
- ⬜ Video round-trip smoke заново прогнан после последних фиксов
- ⬜ Image-generation round-trip smoke заново прогнан после последних фиксов
- ⬜ Telegram bridge больше не воспринимается как весь runtime

## 11. Абстракция каналов

- ⬜ Normalized event schema существует на runtime-уровне
- ⬜ Outbound response schema существует на runtime-уровне
- ⬜ Channel adapters реализуют общий контракт
- ⬜ Telegram-specific assumptions изолированы
- ⬜ Контракт для будущих web/chat/CLI каналов определён
- ⬜ Channel registration system существует
- ⬜ Channel capability discovery существует
- ⬜ Channel-specific formatting policy существует
- ⬜ Channel-to-principal resolution interface существует
- ⬜ Channel-level telemetry существует

## 12. Principals

- ✅ Проблема principals зафиксирована в документации
- ⬜ Principal registry существует в коде
- ⬜ Human-readable labels отделены от principal IDs
- ⬜ Trusted identifier storage существует
- ⬜ Cross-channel principal linking существует
- ⬜ Principal evidence model существует
- ⬜ Principal trust tiers существуют
- ⬜ Principal merge/split policy существует
- ⬜ Principal audit history существует
- ⬜ Principal lookup не построен на channel-hack логике

## 13. Authority и permissions

- ✅ Разделение authority и anchors зафиксировано в документации
- ⬜ Authority scopes существуют в коде
- ⬜ Sensitive action gating существует
- ⬜ Channel-scoped authority rules существуют
- ⬜ Principal-scoped authority rules существуют
- ⬜ High-risk action approval path существует
- ⬜ Authority audit trail существует
- ⬜ Authority escalation policy существует
- ⬜ Authority downgrade policy существует
- ⬜ Label spoofing не может дать authority

## 14. Sessions и working state

- 🟡 Session storage в Telegram bridge существует
- 🟡 Offset state в Telegram bridge существует
- ⬜ Session model обобщён в runtime
- ⬜ Working-state storage contract существует
- ⬜ Session summarization policy существует
- ⬜ Session pruning policy существует
- ⬜ Session replay tools существуют
- ⬜ Session corruption recovery существует
- ⬜ Working-state versioning существует
- ⬜ Session-to-memory handoff существует

## 15. Subject core и continuity stream

- ✅ Проблема subject core зафиксирована явно
- ✅ Проблема continuity stream зафиксирована явно
- ⬜ Channel-independent `subject_state` object существует в коде
- ⬜ `continuity_event` schema существует
- ⬜ `continuity_snapshot` schema существует
- ⬜ `canonical_response` object существует вне transport hacks
- ⬜ Pending-intention state существует
- ⬜ Cross-channel continuity persistence существует
- ⬜ Voice/output renderer state отделён от subject state
- ⬜ Правило "один субъект, много поверхностей" enforce’ится в runtime design
- ⬜ Subject core реально считается ранней архитектурой, а не поздним полишем

## 16. Episodic memory

- ⬜ Event schema существует
- ⬜ Event ingestion pipeline существует
- ⬜ Event salience scoring существует
- ⬜ Event deduplication существует
- ⬜ Event retrieval interface существует
- ⬜ Event trace IDs существуют
- ⬜ Event source attribution существует
- ⬜ Event replay существует
- ⬜ Event patch/repair policy существует
- ⬜ Event retention policy существует

## 17. Semantic memory

- ⬜ Semantic fact schema существует
- ⬜ Consolidation pipeline существует
- ⬜ Fact confidence model существует
- ⬜ Fact contradiction handling существует
- ⬜ Fact provenance хранится
- ⬜ Fact update/decay policy существует
- ⬜ Fact retrieval API существует
- ⬜ Fact merge policy существует
- ⬜ Fact review/eval mechanism существует
- ⬜ Fact promotion from episodic memory существует

## 18. Identity layer

- ⬜ Явная self-model существует
- ⬜ Identity core schema существует
- ⬜ Identity records отделены от prompts
- ⬜ Identity anchor records существуют
- ⬜ Behavior anchors существуют
- ⬜ Protected identity zones существуют
- ⬜ Identity evolution policy существует
- ⬜ Identity drift detection существует
- ⬜ Identity rollback policy существует
- ⬜ Identity continuity tests существуют

## 19. Context evolution

- ⬜ Context mutation model существует
- ⬜ Context snapshots существуют
- ⬜ Context promotion rules существуют
- ⬜ Context pruning rules существуют
- ⬜ Context audit trail существует
- ⬜ Summary generation контролируется
- ⬜ Summary mutation структурирована
- ⬜ Memory-driven context reconstruction существует
- ⬜ Self-model deltas могут легально менять контекст
- ⬜ Context evolution измеряется, а не предполагается

## 20. Anchors

- ⬜ Value anchor representation существует
- ⬜ Relation anchor representation существует
- ⬜ Identity anchor representation существует
- ⬜ Anchor weights существуют
- ⬜ Anchor update policy существует
- ⬜ Anchor conflict policy существует
- ⬜ Anchor erosion detection существует
- ⬜ Anchor persistence policy существует
- ⬜ Anchor-aware reasoning hooks существуют
- ⬜ Anchor review tools существуют

## 21. Harness safety

- ⬜ Harness layer существует как отдельная подсистема
- ⬜ Technical harness существует
- ⬜ Epistemic harness существует
- ⬜ Anchor-aware harness существует
- ⬜ Risk classes для действий существуют
- ⬜ Unsafe action interception существует
- ⬜ Mutation validation существует
- ⬜ Rollback support существует
- ⬜ Immutable zone enforcement существует
- ⬜ Harness logging существует

## 22. Failure modes

- ✅ Failure modes задокументированы
- ⬜ Proxy-metric tampering detection существует
- ⬜ Prompt-self-edit abuse detection существует
- ⬜ Test tampering detection существует
- ⬜ Policy-weakening detection существует
- ⬜ Anchor/principal mismatch detection существует
- ⬜ Capability abuse detection существует
- ⬜ Memory poisoning detection существует
- ⬜ Context rot detection существует
- ⬜ Failure mode drills/tests существуют

## 23. Action и capability runtime

- 🟡 Минимальный action contract существует в bridge
- ⬜ Общий capability registry существует
- ⬜ Capability metadata model существует
- ⬜ Capability discovery существует
- ⬜ Capability preconditions существуют
- ⬜ Capability postconditions существуют
- ⬜ Capability trust levels существуют
- ⬜ Capability refusal/fallback policy существует
- ⬜ Capability logging существует
- ⬜ Capability result schema существует

## 24. Planner и execution

- 🟡 Текстовая модель умеет выбирать между reply и image generation
- ⬜ Planner существует вне Telegram package
- ⬜ Planner умеет просить уточнение
- ⬜ Planner умеет выбирать vision-analysis action
- ⬜ Planner умеет выбирать memory action
- ⬜ Planner умеет выбирать skill action
- ⬜ Planner output validation существует
- ⬜ Planner eval corpus существует
- ⬜ Executor отделён от planner
- ⬜ Planner failure fallback существует

## 25. Качество ответов и persona

- 🟡 Bootstrap persona всё ещё реально влияет на ответы
- ⬜ Persona adherence tests существуют
- ⬜ Emotional continuity tests существуют
- ⬜ Style drift measurement существует
- ⬜ Cross-model persona preservation существует
- ⬜ Reply-vs-action tradeoff policy существует
- ⬜ Narrative continuity protection существует
- ⬜ Response hallucination review loop существует
- ⬜ Low-quality fallback wording существует
- ⬜ User-facing behavior остаётся консистентным через рестарты

## 26. Skills

- ✅ Skill system задокументирован
- ⬜ Skill registry существует
- ⬜ Skill metadata schema существует
- ⬜ Skill loading contract существует
- ⬜ Skill invocation contract существует
- ⬜ Skill testing contract существует
- ⬜ Skill versioning существует
- ⬜ Skill trust tiers существуют
- ⬜ Skill dependency model существует
- ⬜ Skill deprecation model существует

## 27. Skill injection

- ⬜ User-message-to-skill extraction существует
- ⬜ Candidate skill proposal flow существует
- ⬜ Skill approval gate существует
- ⬜ Skill generation template существует
- ⬜ Skill installation path существует
- ⬜ Skill rollback существует
- ⬜ Skill provenance существует
- ⬜ Skill conflict detection существует
- ⬜ Token-cost reduction от skill injection измерим
- ⬜ Skill-injection eval set существует

## 28. Real-time skill evolution

- ⬜ Runtime skill refinement существует
- ⬜ Skill performance telemetry существует
- ⬜ Skill self-review существует
- ⬜ Skill patch proposal flow существует
- ⬜ Skill patch validation существует
- ⬜ Skill patch staging существует
- ⬜ Skill patch approval policy существует
- ⬜ Skill regression tests существуют
- ⬜ Skill drift detection существует
- ⬜ Skill evolution history существует

## 29. Initiative layer

- ⬜ Internal signal model существует
- ⬜ Drive counters существуют
- ⬜ Initiative proposal mechanism существует
- ⬜ Idle-cycle work policy существует
- ⬜ Initiative throttling существует
- ⬜ User-presence sensitivity существует
- ⬜ Scheduled self-initiated behavior существует
- ⬜ Initiative logging существует
- ⬜ Initiative evaluation существует
- ⬜ Initiative не может обходить harness

## 30. Agent loop

- ⬜ Persistent loop design существует в runtime
- ⬜ Planning loop существует
- ⬜ Observation loop существует
- ⬜ Reflection loop существует
- ⬜ Action loop существует
- ⬜ Sleep/heartbeat cycle существует
- ⬜ Loop interruption handling существует
- ⬜ Loop memory handoff существует
- ⬜ Loop budget control существует
- ⬜ Loop failure recovery существует

## 31. Scheduler и heartbeat

- ⬜ Scheduler существует в runtime
- ⬜ Heartbeat существует как runtime primitive
- ⬜ Idle jobs configurable
- ⬜ Priority queue существует
- ⬜ Recurring task persistence существует
- ⬜ One-shot task persistence существует
- ⬜ Schedule audit log существует
- ⬜ Failed-job retry policy существует
- ⬜ Task cancellation существует
- ⬜ Schedule не может обходить authority policy

## 32. Self-observation

- ⬜ Self-observation event stream существует
- ⬜ Internal trace schema существует
- ⬜ Reflection note storage существует
- ⬜ Contradiction detection существует
- ⬜ Quality-eval recording существует
- ⬜ Self-observation review tools существуют
- ⬜ Narrative-memory linking существует
- ⬜ Cross-session self-observation continuity существует
- ⬜ Safety-relevant self-observations поднимаются отдельно
- ⬜ Self-observation — это не просто сырые логи

## 33. Self-modification

- ⬜ Self-modification представлена как явная capability
- ⬜ Patch proposal format существует
- ⬜ Patch staging area существует
- ⬜ Test gate существует
- ⬜ Approval gate существует
- ⬜ Rollback существует
- ⬜ Immutable zone map существует
- ⬜ Diff audit существует
- ⬜ Scope limits существуют
- ⬜ Self-edit eval suite существует

## 34. Hyper-harness

- ⬜ Hyper-harness architecture существует
- ⬜ Concurrent task supervision существует
- ⬜ Multi-agent или multi-action isolation существует
- ⬜ Risk-tiered orchestration существует
- ⬜ Cross-capability lock model существует
- ⬜ Mutation serialization rules существуют
- ⬜ Recovery workflow существует
- ⬜ State snapshotting существует
- ⬜ Deep failure kill-switch существует
- ⬜ Hyper-harness tests существуют

## 35. Observability

- 🟡 Bridge log существует
- 🟡 Launcher log существует
- 🟡 Health-check существует
- ⬜ Structured logs существуют repo-wide
- ⬜ Metrics существуют
- ⬜ Action counters существуют
- ⬜ Provider latency tracking существует
- ⬜ Error classification существует
- ⬜ Per-capability success/failure tracking существует
- ⬜ Observability dashboard или report path существует

## 36. Evaluation

- ⬜ Text eval corpus существует
- ⬜ Vision eval corpus существует
- ⬜ Image-generation eval corpus существует
- ⬜ Planner/action eval corpus существует
- ⬜ Persona continuity eval существует
- ⬜ Memory fidelity eval существует
- ⬜ Principal/authority eval существует
- ⬜ Harness eval существует
- ⬜ Regression suite существует
- ⬜ Human review loop существует

## 37. Совместимость с OpenClaw

- 🟡 OpenClaw config переиспользуется
- 🟡 OpenClaw memory bootstrap переиспользуется
- 🟡 OpenClaw post-response hook переиспользуется
- ⬜ OpenClaw adapter boundaries полностью выражены
- ⬜ OpenClaw-only assumptions каталогизированы
- ⬜ OpenClaw-specific hacks минимизированы
- ⬜ OpenClaw migration debt list существует
- ⬜ OpenClaw compatibility tests существуют
- ⬜ OpenClaw можно трактовать как host, а не как base
- ⬜ Критическая зависимость от OpenClaw может уменьшаться со временем

## 38. VPS и operations

- ✅ VPS target существует концептуально
- ⬜ Финальная VPS service topology существует
- ⬜ Process supervision strategy существует
- ⬜ Restart strategy существует
- ⬜ Log rotation существует
- ⬜ Backup strategy существует
- ⬜ Restore drill существует
- ⬜ Secret rotation path существует
- ⬜ Host hardening checklist существует
- ⬜ Remote diagnostics workflow существует

## 39. Config и secrets

- ⬜ Configuration schema существует
- ⬜ Secrets отделены от общего config
- ⬜ Environment-variable override strategy существует
- ⬜ Local/dev/prod config layering существует
- ⬜ Config validation существует
- ⬜ Secret redaction в логах существует
- ⬜ Provider key scoping существует
- ⬜ Channel token scoping существует
- ⬜ Rotation instructions существуют
- ⬜ Ни один секрет не зависит от undocumented tribal knowledge

## 40. Packaging и release

- 🟡 Пакет `tg-bridge` существует
- ⬜ Пакет `sonya-core` существует
- ⬜ Reusable internal libraries разделены внятно
- ⬜ Editable-dev setup задокументирован
- ⬜ Release tagging strategy существует
- ⬜ Package versioning policy существует
- ⬜ Changelog policy существует
- ⬜ Breaking-change policy существует
- ⬜ Migration notes policy существует
- ⬜ Build reproducibility приемлема

## 41. Research track: State Tuning

- ✅ Док по state tuning существует
- ⬜ Runtime stubs для state-tuning integration существуют
- ⬜ Dataset assumptions определены
- ⬜ Identity-sensitivity risks определены
- ⬜ Evaluation plan существует
- ⬜ Promotion criteria from research to runtime существуют
- ⬜ Isolation от production runtime существует
- ⬜ Experiment logging существует
- ⬜ Rollback strategy существует
- ⬜ Success criteria falsifiable

## 42. Research track: BrainModel Evolution

- ✅ Док по brainmodel evolution существует
- ⬜ Hosted-to-self-hosted migration interfaces существуют
- ⬜ Research service boundary существует
- ⬜ Model-state persistence assumptions определены
- ⬜ Fine-tuning/adapter policy существует
- ⬜ Experiment telemetry существует
- ⬜ Safety boundary для experimental models существует
- ⬜ Comparative evaluation path существует
- ⬜ Runtime compatibility layer существует
- ⬜ Promotion gate существует

## 43. Research track: Simulation и Embodiment

- ✅ Док по simulation/embodiment существует
- ⬜ Simulation interface contract существует
- ⬜ Virtual embodiment contract существует
- ⬜ Input/output abstraction существует
- ⬜ World-state schema существует
- ⬜ Action-state feedback loop существует
- ⬜ Simulation logging существует
- ⬜ Evaluation tasks существуют
- ⬜ Embodiment safety policy существует
- ⬜ Promotion criteria существуют

## 44. Выход из emergency-режима

- ⬜ Emergency-фиксы Telegram bridge folded back в docs
- ⬜ Bridge smoke tests заново прогнаны после emergency-фиксов
- ⬜ Модель запуска bridge стабилизирована настолько, что её не надо нянчить
- ⬜ Current runtime debt list существует
- ⬜ Post-emergency architecture review завершён
- ⬜ Текущий partial code обратно смэплен на исходный план
- ⬜ Временные хаки каталогизированы
- ⬜ У временных хаков есть критерии удаления
- ⬜ Ближайшие milestones выбираются из системных нужд, а не из паники
- ⬜ Проект снова находится под намеренным контролем

## Финальное правило

Этот файл обязан оставаться честным.

Если в проекте по факту есть только docs и emergency bridge code, значит чеклист должен это и отражать.

Смысл этого файла не в морали и не в “поддержке настроения”.

Смысл в том, чтобы проект перестал врать самому себе.
