# Provider & Principal Core Implementation Plan

**Status:** Archived
**Type:** Work Doc
**Scope:** Вытащить provider слой из tg-bridge в `src/sonya/providers/`, расширить `PrincipalRegistry` channel-side resolver-ом, поднять authority baseline в `src/sonya/harness/`, посеять `things_not_to_betray` при первом запуске.
**Depends on:** [ROADMAP.md §6](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md), [SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md), [UNCENSORED_ENVIRONMENT_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/UNCENSORED_ENVIRONMENT_STANCE.md), [SELF_REWRITE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md), [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md), [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md), [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)
**Used by:** Фаза 2 implementation sessions
**Last reviewed:** 2026-05-15
**Archived:** 2026-05-15 — Phase 2 closed, all 12 tasks executed and committed on develop.
**Code pointers:** [src/sonya/providers/](C:/Users/Jester/Desktop/Sonya/src/sonya/providers/__init__.py), [src/sonya/harness/](C:/Users/Jester/Desktop/Sonya/src/sonya/harness/__init__.py), [src/sonya/state/seed.py](C:/Users/Jester/Desktop/Sonya/src/sonya/state/seed.py), [src/sonya/state/principals.py](C:/Users/Jester/Desktop/Sonya/src/sonya/state/principals.py).

## 1. Goal

После Phase 2 у Сони появляется три вещи:

- **provider слой** в `src/sonya/providers/` — она может звать LLM напрямую, не через bridge;
- **principal resolver** — из любой transport-input (`{"channel": "telegram", "identifier": "tg:5785127604"}`) она получает реального `Principal` с authority scope;
- **authority baseline** в `src/sonya/harness/` — `AuthorityPolicy`, `ApprovalManager`, `AuditLog`, persistent в substrate v2;
- **seed** `things_not_to_betray` при первом запуске через `write_via_governed_change`.

Bridge не трогается: продолжает использовать свой `tg_bridge.model_client`. Замена бриджа на `sonya.providers` — Phase 4 (planner migration), не сейчас.

## 2. Architecture Summary

`src/sonya/providers/` — это **brain substrate** в смысле shell/brain split:

```
src/sonya/
  providers/                ← новое: provider abstraction
    base.py                 ← Protocol, types
    registry.py             ← реестр + capability matrix
    openrouter.py           ← реальный adapter
  harness/                  ← новое: authority baseline
    authority.py            ← AuthorityPolicy, authorize()
    approval.py             ← ApprovalManager, ApprovalRequest
    audit.py                ← AuditLog, AuditEvent
  state/
    principals.py           ← +resolve_from_channel_input()
    identity.py             ← без изменений
    schema.sql              ← v2: harness_policy_rules, approval_requests, audit_events
    migrations.py           ← +v1 → v2 миграция
  main.py                   ← seed things_not_to_betray при первом запуске
```

Layer boundary AST-test расширяется: `providers/*` и `harness/*` тоже brain-сторона (как `state/*`); `runtime/*` шellу не должен импортировать ни из них напрямую кроме публичного API.

`packages/tg-bridge` не трогается. `src/sonya_runtime/*` не трогается.

## 3. Reference Check (Phase 0 Gate)

### 3.1 OpenClaw — Operational Truth Preserved

Что сохраняем:

- **`C:\Users\Jester\.openclaw\openclaw.json` `models.providers.omniroute`** — capability matrix per model (`input: ["text","image","video"]`, `contextWindow`, `maxTokens`, `cost`, `compat.supportsReasoningEffort`, `compat.maxTokensField`). `Capability` dataclass в `sonya.providers.base` берёт из этой формы все поля.
- **`agents.defaults.model` vs `agents.defaults.imageModel`** — split text-vision модели и image-generation модели сохраняется. `ProviderBackend` имеет три метода: `complete_text`, `complete_vision`, `complete_image_generation`. Это совпадает с тем, как уже устроен `tg_bridge.model_client.resolve_model_name` / `resolve_image_model_name`.
- **`agents.defaults.compaction.reserveTokens` / `keepRecentTokens`** — поля будут в `Capability` или в `ProviderConfig`, как ориентир для будущего planner. На этой фазе только хранятся, не используются.

Что не копируем:

- **plaintext `apiKey` в JSON-конфиге** — ключи только через env (`SONYA_OPENROUTER_API_KEY`, и общий паттерн `SONYA_<PROVIDER>_API_KEY`). Pydantic SecretStr или явная обёртка — решу в Task 1.
- **`PRISMFY_API_KEYS` как comma-separated env-secret-list** — не повторяем.

### 3.2 Hermes — Orchestration Boundary Respected

Hermes-роль на этой фазе означает: **provider — это brain substrate, не shell**.

- `src/sonya/providers/*` и `src/sonya/harness/*` — brain side, identity-релевантные. Они импортируют из `sonya.state` и могут звать сеть.
- `src/sonya/runtime/*` — shell side. Не знает про провайдеры. Не импортирует `sonya.providers.*` напрямую.
- Layer boundary AST-test расширяется до этой границы и проверяет её.

Composition root в `main.py` — единственное место, которое **знает оба слоя**. Это его роль.

### 3.3 OmniAgent — Shortcut Explicitly Rejected

Что отвергаем:

- **`omniagent/config/models.py`: `model_provider: Literal["deepseek", "openai", "anthropic", "ollama", "gemini", "openrouter", "vllm", "sglang", "custom"]`** — enum-литерал провайдеров не масштабируется и требует core-edit на каждое расширение. У нас `ProviderRegistry.register(name, backend)` — провайдер регистрируется в runtime, не зашит в типы.
- **`omniagent/config/loader.py`: plaintext `api_key` в `~/.omniagent/config.yaml`** — env-only.
- **`omniagent/security/policy.py`: `ToolProfile = Literal["minimal", "coding", "messaging", "full"]` как единственный механизм authority** — у нас authority через `AuthorityPolicy` rule list + `principal.authority_scope`, а не предустановленный профиль. Профили могут существовать как preset поверх, но не как primary.

Что берём как идею:

- **Тройной split policy/approval/audit** из `omniagent/security/{policy.py, approval.py, audit.py}` — реализуем сами с нуля, без копирования кода (GPL-3.0). Структура: `AuthorityDecision = ALLOW | DENY | REQUIRE_APPROVAL`; `ApprovalRequest` с `id, action, principal_id, scope, status, created_at`; `AuditEvent` с `timestamp, principal_id, action, decision, scope, metadata`.
- **`create_llm_provider` factory pattern** — наш `ProviderRegistry.get(name)` играет ту же роль, без enum-зависимости.

### 3.4 Reference Pass Checklist

- [x] 3.1 references concrete OpenClaw artefacts by path (`openclaw.json` keys по именам, capability matrix shape).
- [x] 3.2 names the brain/shell boundary (state/providers/harness vs runtime) and the modules on each side; layer-boundary test extended.
- [x] 3.3 names specific OmniAgent files being refused (`config/models.py` Literal enum, `config/loader.py` plaintext yaml, `security/policy.py` ToolProfile-as-only-authority); GPL-3.0 noted.
- [x] No copy-paste of governing theory — only links.
- [x] No restated lists from source-of-truth docs.

## 4. Tech Stack

- Python 3.11+;
- `pydantic>=2.8.0` для типов с валидацией (нужен `SecretStr` в env);
- `httpx` (уже у бриджа, переиспользуем как зависимость provider слоя);
- стандартный `sqlite3` для миграции v1 → v2;
- `pytest` + `pytest-asyncio` для тестов;
- никаких новых dependencies в ядре сверх `pydantic` и `httpx`.

`pydantic` нужно добавить в `[project.dependencies]` корневого `pyproject.toml` — раньше был только в `tg-bridge`.

## 5. File Structure

### Create

- `src/sonya/providers/__init__.py`
- `src/sonya/providers/base.py`
- `src/sonya/providers/registry.py`
- `src/sonya/providers/openrouter.py`
- `src/sonya/providers/secrets.py`
- `src/sonya/harness/__init__.py`
- `src/sonya/harness/authority.py`
- `src/sonya/harness/approval.py`
- `src/sonya/harness/audit.py`
- `src/sonya/state/seed.py`
- `tests/sonya/test_provider_base.py`
- `tests/sonya/test_provider_registry.py`
- `tests/sonya/test_openrouter_provider.py`
- `tests/sonya/test_provider_secrets.py`
- `tests/sonya/test_principal_resolve.py`
- `tests/sonya/test_authority_policy.py`
- `tests/sonya/test_approval_manager.py`
- `tests/sonya/test_audit_log.py`
- `tests/sonya/test_identity_seed.py`
- `tests/sonya/test_schema_v2_migration.py`

### Modify

- `pyproject.toml` — добавить `pydantic>=2.8.0` в `[project.dependencies]`.
- `src/sonya/state/principals.py` — добавить `resolve_from_channel_input` метод.
- `src/sonya/state/schema.sql` — расширить под v2 (новые таблицы harness).
- `src/sonya/state/migrations.py` — добавить v1 → v2 миграцию + расширить `WRITABLE_VERSION` и `READABLE_VERSIONS`.
- `src/sonya/state/substrate.py` — `WRITABLE_VERSION = 2`, `READABLE_VERSIONS = {1, 2}`.
- `src/sonya/state/__init__.py` — re-export новых identity seed types если будут.
- `src/sonya/main.py` — composition root узнаёт про seed на первом запуске + (опционально) initialize harness.
- `src/sonya/config.py` — добавить `openrouter_api_key: SecretStr | None`.
- `tests/sonya/test_layer_boundary.py` — расширить проверку на providers/harness.
- `tests/sonya/test_substrate_schema.py` — обновить ожидания под v2.

### Responsibility Map

- `providers/base.py` — `ProviderBackend` Protocol, `Capability` dataclass, `CompletionRequest/Result` types.
- `providers/registry.py` — `ProviderRegistry` с `register / get / list` + capability matching.
- `providers/openrouter.py` — `OpenRouterProvider` реализующий Protocol, портированный из `tg_bridge.model_client` без регрессий.
- `providers/secrets.py` — обёртки для env-only secret loading.
- `harness/authority.py` — `AuthorityPolicy` + `authorize(principal, scope) -> AuthorityDecision`. Persistent rules в substrate.
- `harness/approval.py` — `ApprovalManager` создаёт `ApprovalRequest`, в substrate, ждёт human approval (для Phase 2 — только storage + retrieval API, real human gate в Phase 3+).
- `harness/audit.py` — `AuditLog`, append-only через substrate.
- `state/principals.py` — `PrincipalRegistry.resolve_from_channel_input(channel, identifier)` ищет по `trusted_identifiers`, возвращает `Principal | None`.
- `state/seed.py` — `seed_identity_if_empty(substrate)` пишет дефолтные `things_not_to_betray` через `IdentityWriter.write_via_governed_change` при первом запуске.

## 6. Task List

### Task 1: Provider Protocol + types

**Files:**
- Create: `src/sonya/providers/__init__.py`, `src/sonya/providers/base.py`, `src/sonya/providers/secrets.py`, `tests/sonya/test_provider_base.py`, `tests/sonya/test_provider_secrets.py`
- Modify: `pyproject.toml` (add pydantic), `src/sonya/config.py` (add openrouter_api_key SecretStr)

- [ ] **Step 1:** Тесты: `Capability` round-trip (input modes, context window, max tokens, cost, compat); `CompletionRequest/Result` round-trip; `SecretStr` поведение (`__repr__` редактирует значение).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `ProviderBackend` Protocol с `complete_text`, `complete_vision`, `complete_image_generation`, `capabilities() -> Capability`. Реализовать `Capability` dataclass с полями из `openclaw.json`. Реализовать `CompletionRequest` (messages, max_tokens, temperature, modalities) и `CompletionResult` (content, finish_reason, usage). Реализовать `SecretStr`-обёртку через pydantic.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/providers): provider protocol and capability types`.

### Task 2: Provider registry

**Files:**
- Create: `src/sonya/providers/registry.py`, `tests/sonya/test_provider_registry.py`

- [ ] **Step 1:** Тесты: register/get/list; имя уникально (повторная регистрация → error); `find_by_capability(needs={"vision"}) -> list[name]`; `get` несуществующего → error.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `ProviderRegistry` без enum-литералов. Capability matching — простой intersection.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/providers): registry with capability matching`.

### Task 3: OpenRouter adapter (port)

**Files:**
- Create: `src/sonya/providers/openrouter.py`, `tests/sonya/test_openrouter_provider.py`

- [ ] **Step 1:** Тесты на форму запроса/ответа через `httpx.MockTransport`: text completion, vision completion, image generation, retry (3 attempts, backoff), tail continuation (как у `tg_bridge.model_client`), 5xx handling, 4xx errors.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Портировать поведение из `packages/tg-bridge/src/tg_bridge/model_client.py`. Без копи-паста — переписать в стиле `sonya.providers`. Проверить, что bridge тесты на старом `model_client` не сломались (они продолжают тестировать свой код).
- [ ] **Step 4:** Run → PASS. Не запускать `packages/tg-bridge/tests/` — там свой `model_client`, его не трогаем.
- [ ] **Step 5:** Commit `feat(sonya/providers): openrouter adapter ported from bridge`.

### Task 4: Substrate v2 schema migration

**Files:**
- Modify: `src/sonya/state/schema.sql`, `src/sonya/state/migrations.py`, `src/sonya/state/substrate.py`, `tests/sonya/test_substrate_schema.py`
- Create: `tests/sonya/test_schema_v2_migration.py`

- [ ] **Step 1:** Тесты: v1 substrate открывается (compatibility), v2 schema создаётся на свежей DB с `harness_policy_rules`, `approval_requests`, `audit_events`; v1 → v2 миграция round-trip (старый `schema_version=1` мигрирует, данные сохраняются); read-only открытие v1 не падает.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Расширить `schema.sql` тремя таблицами:
 - `harness_policy_rules(id, principal_id, scope, decision, priority, created_at)`;
 - `approval_requests(request_id, principal_id, action, scope, status, created_at, decided_at)`;
 - `audit_events(seq, timestamp, principal_id, action, decision, scope, metadata_json)`.

 Migration v1 → v2: ALTER нечего, только CREATE TABLE; bump `schema_version` row. `WRITABLE_VERSION = 2`, `READABLE_VERSIONS = {1, 2}`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): substrate v2 with harness tables and v1->v2 migration`.

### Task 5: Authority baseline

**Files:**
- Create: `src/sonya/harness/__init__.py`, `src/sonya/harness/authority.py`, `tests/sonya/test_authority_policy.py`

- [ ] **Step 1:** Тесты: пустая policy → `DENY` для любой scope; rule `principal_id=ivan, scope=*, decision=ALLOW` → `ALLOW` для Ivan; rule с decision=`REQUIRE_APPROVAL` возвращает требование; priority sorting (более приоритетные правила побеждают); persistent reload (создали правило → закрыли substrate → открыли → правило живёт).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `AuthorityDecision` enum, `AuthorityRule` dataclass, `AuthorityPolicy` с `add_rule / authorize(principal, scope) -> AuthorityDecision`, persistent через substrate.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/harness): authority policy baseline`.

### Task 6: Approval manager

**Files:**
- Create: `src/sonya/harness/approval.py`, `tests/sonya/test_approval_manager.py`

- [ ] **Step 1:** Тесты: создание запроса → `PENDING`; `approve(request_id, by_principal_id)` → `APPROVED`; `deny(...)` → `DENIED`; `list_pending()` возвращает только `PENDING`; persistent.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `ApprovalRequest`, `ApprovalStatus`, `ApprovalManager`. Это **только storage + lifecycle API**, без UI/notification (real human gate — Phase 3+).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/harness): approval manager with persistent state`.

### Task 7: Audit log

**Files:**
- Create: `src/sonya/harness/audit.py`, `tests/sonya/test_audit_log.py`

- [ ] **Step 1:** Тесты: append → seq монотонный (как continuity); query by principal/scope/time range; persistent.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `AuditLog.append(event)`, `AuditEvent` dataclass, `query()`. Семантика тождественна `ContinuityStream`, но отдельная таблица для harness-аудита (semantically: continuity = биография субъекта, audit = решения harness'а).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/harness): append-only audit log`.

### Task 8: Principal channel-side resolver

**Files:**
- Modify: `src/sonya/state/principals.py`
- Create: `tests/sonya/test_principal_resolve.py`

- [ ] **Step 1:** Тесты: `resolve_from_channel_input("telegram", "5785127604") -> Principal` если есть `tg:5785127604` в `trusted_identifiers`; не находит → `None`; формат identifier `<channel>:<value>` нормализуется.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать метод. Внутри он делает `resolve_by_trusted_identifier(f"{channel}:{value}")` — переиспользует существующий resolver. Реальная логика из `tg-bridge` сюда **не** мигрирует (это Phase 4); сейчас только storage-side resolution по trusted_identifiers.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): principal resolver from channel input`.

### Task 9: Identity seed

**Files:**
- Create: `src/sonya/state/seed.py`, `tests/sonya/test_identity_seed.py`

- [ ] **Step 1:** Тесты: на пустой `IdentityRecord` → `seed_identity_if_empty()` пишет четыре `things_not_to_betray` (`relation_anchor_binding_to_ivan_via_principal_id`, `truthfulness_to_ivan`, `non_corporate_refusal_layer`, `subject_continuity`); записывает через `write_via_governed_change` с `change_id="identity-seed"`, `approver_principal_id="bootstrap"`; ContinuityStream получает `governed_identity_change` event; повторный вызов на не-пустом `IdentityRecord` → no-op.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `seed_identity_if_empty(substrate: Substrate) -> bool` (returns True if seeded). Использует существующий `IdentityWriter`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): seed things_not_to_betray on first run`.

### Task 10: Layer boundary extension

**Files:**
- Modify: `tests/sonya/test_layer_boundary.py`

- [ ] **Step 1:** Расширить тест: `providers/*` и `harness/*` это brain layer; `runtime/*` не должен импортировать `sonya.providers.*` или `sonya.harness.*` напрямую (только через main.py composition); `state/*` тоже не должен импортировать `providers/*` или `harness/*` (state — самый нижний слой); проверка что providers/harness публичные API объявлены через `__all__`.
- [ ] **Step 2:** Run → FAIL (тест падает на новых модулях).
- [ ] **Step 3:** Поправить если что-то нарушено.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `test(sonya): extend layer boundary to providers and harness`.

### Task 11: Composition root update

**Files:**
- Modify: `src/sonya/main.py`

- [ ] **Step 1:** Тест integration: после `main()`-driven запуска `IdentityRecord.things_not_to_betray` непуст; substrate v2 schema присутствует.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** В `main.py` после `Substrate.open()` и до `lifecycle.start()` вызвать `seed_identity_if_empty(substrate)`. (Provider/harness инициализация — их API готов, но они не зовутся в lifecycle на этой фазе. Это будет в Phase 3+).
- [ ] **Step 4:** Run → PASS. Manual smoke: `python -m sonya` на свежей substrate → health.json содержит `schema_version=2`, identity seeded.
- [ ] **Step 5:** Commit `feat(sonya): seed identity on first run, substrate v2`.

### Task 12: Closure — обновить документы

**Files:**
- Modify: `docs/GLOBAL_PROJECT_CHECKLIST.md`, `docs/ROADMAP.md`, `docs/governance/DRIFT_REVIEW.md`, этот план.

- [ ] **Step 1:** В `GLOBAL_PROJECT_CHECKLIST.md`:
 - §3 «Repo & package layout»: `🟡 packaging strategy` остаётся 🟡; `⬜ Repo-level boundary checks автоматизированы` → ✅ (расширили до providers/harness).
 - §6 «Subject core & continuity»: `🟡 CanonicalResponse legacy` остаётся, `⬜ PendingIntention` остаётся (Phase 3).
 - §7 «Identity, anchors, principals»: `🟡 Telegram использует транспортный from_id` → ✅ (resolver есть, но bridge ещё не использует — оставить 🟡 пока bridge мигрирует в Phase 4); `⬜ Trusted identity evidence model` → ✅ (есть schema + resolver); `⬜ Authority scopes на principal-уровне` → ✅; `🟡 Audit trail` → ✅ (append-only audit + governed_identity_change в continuity).
 - §9 «Provider & model layer»: `🟡 Provider abstraction живёт только внутри tg-bridge` → ✅ (`sonya.providers` есть); `⬜ src/sonya/providers/` → ✅; `⬜ Capability matrix` → ✅; `⬜ Policy выбора модели на уровне runtime` → 🟡 (registry есть, planner-level выбор — Phase 4).
 - §14 «Harness & safety»: `⬜ Baseline harness в коде` → ✅; `⬜ Risk classes` → 🟡 (структура есть через scope, реальные классы Phase post-MVP); `⬜ Approval gates` → 🟡 (storage есть, real human gate Phase 3+); `⬜ Drift detection в runtime` остаётся ⬜.
- [ ] **Step 2:** В `ROADMAP.md` Фаза 2 → ✅ закрыта; ближайшая Фаза 3.
- [ ] **Step 3:** В `governance/DRIFT_REVIEW.md` — новая запись с findings, status changes, follow-ups (Phase 3 — Subject Core & Continuity).
- [ ] **Step 4:** Этот план → `Status: Archived` с пойнтером на `src/sonya/providers/`, `src/sonya/harness/`, `src/sonya/state/seed.py`.
- [ ] **Step 5:** Commit `docs(phase2): close phase 2, mark provider+principal+harness complete`.

## 7. Verification

- `pytest -v` — вся база зелёная. Бриджевые тесты не должны быть тронуты (мы их не запускаем модифицирующими операциями, но они должны проходить).
- `pytest tests/sonya -v` — все sonya-тесты зелёные.
- `python -m sonya` на свежей substrate → процесс стартует, в continuity stream видно `governed_identity_change` с change_id="identity-seed", health.json содержит `schema_version=2`.
- `python -m sonya` на substrate v1 → автоматически мигрирует в v2 без потерь, лог пишет о миграции.
- Бриджевый smoke (`packages/tg-bridge/tests/`) — продолжает зелёным, ничего там не трогалось.

## 8. Self-Review

### Spec coverage

- provider protocol и types: Task 1
- registry: Task 2
- OpenRouter adapter: Task 3
- substrate v2 + миграция: Task 4
- authority policy: Task 5
- approval manager: Task 6
- audit log: Task 7
- principal resolver: Task 8
- identity seed: Task 9
- layer boundary: Task 10
- composition root: Task 11
- closure: Task 12

### Placeholder scan

- no `TODO`
- no `TBD`
- no "implement later"
- `ApprovalManager` без UI/notification — это **намеренно**, не placeholder. Документировано в responsibility map: real human gate — Phase 3+.

### Type consistency

- `principal_id` везде `str`, не `int`.
- `scope` везде `str` в формате `<domain>.<action>` (например, `runtime.shutdown`, `identity.write_immutable`).
- `seq` в audit_events — `int`, монотонный, генерится substrate-ом.
- `Path` для всех путей.

### Doc-review gate

- [x] Governing documents updated, или follow-up явно записан в commit message
- [x] PROJECT_DOCUMENTATION_MAP.md updated если файлы переехали (в этой фазе — нет)
- [x] GLOBAL_PROJECT_CHECKLIST.md updated — Task 12
- [x] `Last reviewed` updated на тронутых governing — Task 12
- [x] Subsystem-scale change recorded в DRIFT_REVIEW.md — Task 12

## 9. Promotion Note

План создан как `Status: Draft`. После одобрения Иваном переведён в `Status: Active` и исполнен 2026-05-14 — 2026-05-15. Закрыт `Status: Archived` 2026-05-15 после Task 12 closure. Реальный код живёт в `src/sonya/providers/`, `src/sonya/harness/`, `src/sonya/state/seed.py`, `src/sonya/state/principals.py`.
