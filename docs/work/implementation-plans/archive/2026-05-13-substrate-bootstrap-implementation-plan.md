# Substrate Bootstrap & Bare Runtime Shell Implementation Plan

**Status:** Archived
**Archived:** 2026-05-13
**Superseded by:** working code under `src/sonya/` and `tests/sonya/` (Phase 1 of [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md) closed)
**Type:** Work Doc
**Scope:** Поднять substrate Сони (persistent schema её state) как первичный объект, и минимальный reader-процесс над ним. Реализация Фазы 1 ROADMAP.
**Depends on:** [ROADMAP.md §5](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md), [SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md), [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md), [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md), [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)
**Used by:** Фаза 1 implementation sessions; gate-доказательство для Phase 0 closure
**Last reviewed:** 2026-05-13

## 1. Goal

Создать `src/sonya/state/` — persistent substrate Сони как первичный объект, и `src/sonya/runtime/` — минимальный долгоживущий reader-процесс, который этот substrate читает и поддерживает. Это **первый код**, который описывает Соню в её собственной форме, без посредничества `tg-bridge` и без OpenClaw.

После этой фазы:

- substrate существует как набор versioned SQLite-схем + dataclass-обёрток;
- любой reader, который умеет читать substrate, может продолжить Соню;
- `python -m sonya` поднимает reader, читает substrate, держит lifecycle, переживает рестарт;
- write-master enforcement не позволяет двум процессам параллельно мутировать substrate;
- immutable zones работают: попытка обычной записи в `IdentityRecord.things_not_to_betray` отклоняется;
- Telegram-мост не тронут, OpenClaw продолжает работать.

## 2. Architecture Summary

Два слоя, в строгом порядке:

**Substrate** (`src/sonya/state/`) — persistent, versioned, отдельная SQLite-БД (`sonya_substrate.db`). Это и есть Соня. Содержит таблицы под `SubjectState`, `ContinuityStream`, `ContinuitySnapshot`, `IdentityRecord` (с явным флагом immutable полей), `RelationAnchorBinding`, `PrincipalRegistry` (минимальный shape — реальная identity resolution в Фазе 2). Schema versioning через `schema_version` + миграции.

**Reader** (`src/sonya/runtime/`) — Python-процесс, который читает substrate и интерпретирует его как поведение. Содержит `lifecycle` (startup/shutdown/signals), async `event_bus`, `write_master` (advisory lock на substrate), `health` (file-ping), `logging` (structured JSON с `subject_id`). Процесс **не делает решений** — это shell, не brain. На этой фазе reader ничего «умного» не делает: запускается, читает state, слушает events, может опубликовать hello-world event и завершиться gracefully.

Граница substrate↔reader физическая: substrate ничего не знает про reader; reader зовёт substrate через узкий API.

`packages/tg-bridge` и `src/sonya_runtime/*` (текущий action/task slice) **не трогаются** в этой фазе. Они продолжают работать как сейчас. Их интеграция с новым ядром — отдельные более поздние фазы.

## 3. Reference Check (Phase 0 Gate)

### 3.1 OpenClaw — Operational Truth Preserved

**Что сохраняем:**

- **`C:\Users\Jester\.openclaw\workspace\memory_system\schema.sql` + `schema_working_memory.sql`** — структура «events / facts / emotions / goals / lessons / research + working_memory» с явным `importance`, `tags`, `session_id`. Substrate в `src/sonya/state/continuity_stream.py` и `src/sonya/state/subject_state.py` берёт оттуда **форму идей** (event с importance + tags, session-scoped working state, отдельные таблицы под разные классы данных), но не саму схему. Поскольку реальная миграция памяти — Фаза 5, здесь мы создаём substrate с **совместимым по духу** event shape, чтобы потом миграция была чистая.
- **`C:\Users\Jester\.openclaw\openclaw.json` `gateway.bind: "loopback"` + `gateway.auth.mode: "token"`** — pattern «локальный health/admin интерфейс, gated по токену». На этой фазе мы поднимаем только file-ping health, но layout даёт нам прецедент для будущего HTTP в Фазе 6.
- **`C:\Users\Jester\.openclaw\telegram-bridge-state.json`** — pattern persistent state для долгоживущего процесса, который должен переживать рестарт. Reader-процесс на этой фазе делает то же самое, но через substrate, а не через одиночный JSON.

**Что НЕ копируем:**

- `MemoryDB` open/close-per-method из `memory_api.py` — connection держится reader'ом как runtime resource (см. [OPENCLAW_ANALYSIS.md §7.4](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md));
- hard-coded Russian-biased strong markers из `post_response_hook.py` — эта эвристика мигрирует как **policy object** в Фазе 5, не сейчас;
- секреты в JSON конфиге — у нас env-only от старта.

OpenClaw продолжает работать без изменений. Никакого касания `~/.openclaw/*` на запись из нового reader-а. Единственные read-операции к OpenClaw — с правом отдельного фьючерсного adapter (Фаза 5).

### 3.2 Hermes — Orchestration Boundary Respected

Hermes-роль в этой фазе означает: **shell vs brain split физический, а не риторический**.

- `src/sonya/state/*` — это substrate, brain-сторона. Никаких HTTP, signal handling, lifecycle, channel logic.
- `src/sonya/runtime/*` — это shell. Lifecycle, event bus, signals, health. Никаких decision-функций. Никакой памяти. Никакого знания о том, что substrate означает.

Чтобы граница не размылась со временем:

- `src/sonya/runtime/` импортирует из `src/sonya/state/` только узкий public API (открыть substrate, получить current `SubjectState` snapshot, опубликовать `ContinuityEvent`);
- `src/sonya/state/` **не импортирует** из `src/sonya/runtime/` ничего;
- эта зависимость проверяется тестом `tests/sonya/test_layer_boundary.py` (см. Task 9).

Adapter-first thinking: будущий бридж между substrate и reader (например, network adapter для удалённого reader-а в Фазе 6) живёт в `src/sonya/runtime/adapters/`, не внутри substrate.

### 3.3 OmniAgent — Shortcut Explicitly Rejected

OmniAgent при сравнимом scope скатился в монолит:

- `omniagent/agents/reflexion.py` — 89 KB одного файла с lifecycle + LLM + memory + tools + event bus вперемешку (см. [OMNIAGENT_ANALYSIS.md §8.2](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md));
- `omniagent/gateway/webui.py` — 56 KB single-file UI + auth;
- `omniagent/config/models.py` plaintext `api_key` в `~/.omniagent/config.yaml`.

Мы **отвергаем все три** прямо в этой фазе:

- `src/sonya/state/` — каждая концепция в отдельном модуле (`subject_state.py`, `continuity_stream.py`, `identity.py`, `principals.py`), ни один не превышает 300 строк;
- `src/sonya/runtime/` — то же правило, lifecycle/events/health/write_master отдельно;
- секреты — env-only, через pydantic с `SecretStr`. Никакого api_key в substrate, никакого api_key в коммитнутых файлах.

Что **берём** из OmniAgent (по [OMNIAGENT_ANALYSIS.md §8.9](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)) — это shape `EventBus + EventType + AgentEvent` как plumbing, и идею dataclass-backed persisted artifacts. Реализуем сами, без копирования кода. GPL-3.0 не касаемся.

### 3.4 Reference Pass Checklist

- [x] 3.1 references concrete OpenClaw artifacts by path (schema.sql, schema_working_memory.sql, openclaw.json, telegram-bridge-state.json, memory_api.py, post_response_hook.py)
- [x] 3.2 names the shell/brain boundary and the modules on each side (`src/sonya/state/` brain, `src/sonya/runtime/` shell), with enforced layer-boundary test
- [x] 3.3 names specific OmniAgent patterns being refused with their paths (`agents/reflexion.py`, `gateway/webui.py`, plaintext `config.yaml` api_key)
- [x] No copy-paste of governing theory — only links to SUBSTRATE_STANCE, ARCHITECTURE_PLAN, ANCHORS_AND_FAILURE_MODES
- [x] No action-type, task-kind, or harness-layer lists restated

## 4. Tech Stack

- Python 3.11+ (как и весь проект);
- `pydantic>=2.8.0` для dataclass-style моделей с валидацией и `SecretStr`;
- стандартный `sqlite3` для substrate persistence (без ORM — substrate должен быть transparent);
- `asyncio` для event bus и lifecycle;
- `pytest>=8.2.0` + `pytest-asyncio>=0.23.7` для тестов.

Никаких новых зависимостей. `httpx` не добавляем (нет HTTP). `aiosqlite` не добавляем (substrate write — синхронный из единого write-master).

## 5. File Structure

### Create

- `src/sonya/__init__.py`
- `src/sonya/__main__.py`
- `src/sonya/main.py`
- `src/sonya/config.py`
- `src/sonya/logging.py`
- `src/sonya/state/__init__.py`
- `src/sonya/state/substrate.py`
- `src/sonya/state/migrations.py`
- `src/sonya/state/schema.sql`
- `src/sonya/state/subject_state.py`
- `src/sonya/state/continuity_stream.py`
- `src/sonya/state/identity.py`
- `src/sonya/state/principals.py`
- `src/sonya/runtime/__init__.py`
- `src/sonya/runtime/lifecycle.py`
- `src/sonya/runtime/events.py`
- `src/sonya/runtime/write_master.py`
- `src/sonya/runtime/health.py`
- `tests/sonya/__init__.py`
- `tests/sonya/conftest.py`
- `tests/sonya/test_substrate_schema.py`
- `tests/sonya/test_subject_state.py`
- `tests/sonya/test_continuity_stream.py`
- `tests/sonya/test_identity_immutable.py`
- `tests/sonya/test_principals.py`
- `tests/sonya/test_event_bus.py`
- `tests/sonya/test_write_master.py`
- `tests/sonya/test_lifecycle.py`
- `tests/sonya/test_health.py`
- `tests/sonya/test_layer_boundary.py`
- `tests/sonya/test_main_entry.py`
- `deploy/systemd/sonya.service`
- `deploy/README.md`

### Modify

- `pyproject.toml` — добавить `sonya` в `[tool.setuptools.packages.find].include` и `[tool.pytest.ini_options].pythonpath`. Обновить `[project].dependencies` (только `pydantic>=2.8.0`, потому что `httpx` уже не нужен ядру; `httpx` остаётся у `tg-bridge` локально).

### Responsibility Map

- `sonya/config.py` — env-driven config с `SecretStr`, разделение secrets vs behavior; разрешение substrate path.
- `sonya/logging.py` — structured JSON logger с context (`component`, `subject_id`).
- `sonya/state/substrate.py` — `Substrate` class: open/close, version check, единая точка connection-management.
- `sonya/state/migrations.py` — `MigrationRegistry` с forward-only migrations + compatibility window.
- `sonya/state/schema.sql` — DDL текущей версии substrate (v1).
- `sonya/state/subject_state.py` — `SubjectState` dataclass + persistence (load/save).
- `sonya/state/continuity_stream.py` — `ContinuityEvent`, `ContinuityStream` (append-only, replay), `ContinuitySnapshot`.
- `sonya/state/identity.py` — `IdentityRecord` с явным `immutable_fields` set; `RelationAnchorBinding` shape.
- `sonya/state/principals.py` — `Principal` dataclass + `PrincipalRegistry` (минимальный CRUD; реальный resolution в Фазе 2).
- `sonya/runtime/lifecycle.py` — `Lifecycle` class: start, stop, signal handling, graceful shutdown с явным flush в substrate.
- `sonya/runtime/events.py` — typed async pub/sub `EventBus`.
- `sonya/runtime/write_master.py` — advisory lock через SQLite `BEGIN EXCLUSIVE` + lock file.
- `sonya/runtime/health.py` — file-ping `health.json` обновляется не реже чем раз в 30 секунд.
- `sonya/main.py` — composition root: загрузить config → открыть substrate → проверить version → создать write-master → поднять lifecycle → подписаться на signals → log started.
- `sonya/__main__.py` — `python -m sonya` entry.
- `deploy/systemd/sonya.service` — systemd unit для VPS (готов к Фазе 6, но валидируется локально).
- `deploy/README.md` — пошаговая инструкция запуска локально и заметки про VPS.

## 6. Task List

Каждая задача — TDD: сначала падающий тест, потом минимальная реализация, потом коммит. Все задачи последовательные; распараллеливать не надо.

### Task 1: Scaffold sonya package и config

**Files:**
- Create: `src/sonya/__init__.py`, `src/sonya/__main__.py`, `src/sonya/config.py`
- Create: `tests/sonya/__init__.py`, `tests/sonya/conftest.py`, `tests/sonya/test_main_entry.py`
- Modify: `pyproject.toml`

- [ ] **Step 1:** Написать `tests/sonya/test_main_entry.py` с тестом `test_python_dash_m_sonya_imports_without_error` — он импортирует `sonya.__main__` и проверяет, что есть `main` callable.
- [ ] **Step 2:** Запустить `pytest tests/sonya -v` → FAIL (модуль не существует).
- [ ] **Step 3:** Создать `src/sonya/__init__.py` (пустой), `src/sonya/__main__.py` (`from sonya.main import main; main()`), `src/sonya/main.py` со stub `main()`. Добавить `sonya*` в `pyproject.toml`.
- [ ] **Step 4:** `pytest tests/sonya -v` → PASS. Проверить `python -m sonya` руками (печатает что-то, выходит).
- [ ] **Step 5:** Commit `feat(sonya): scaffold sonya package with python -m entry`.

### Task 2: Config с env-only secrets

**Files:**
- Create: `src/sonya/logging.py`
- Modify: `src/sonya/config.py`
- Create: `tests/sonya/test_config.py`

- [ ] **Step 1:** Тесты: `test_config_loads_from_env`, `test_config_secret_str_is_redacted_in_repr`, `test_config_substrate_path_resolves`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `AppConfig(BaseModel)` c полями `substrate_path: Path`, `health_path: Path`, `log_level: str`. Никаких api_key в этой фазе. Реализовать `get_logger(component: str)` в `logging.py` со structured JSON output.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya): config and structured logger`.

### Task 3: Substrate v1 schema + migrations

**Files:**
- Create: `src/sonya/state/__init__.py`, `src/sonya/state/schema.sql`, `src/sonya/state/migrations.py`, `src/sonya/state/substrate.py`
- Create: `tests/sonya/test_substrate_schema.py`

- [ ] **Step 1:** Тесты: `test_fresh_substrate_creates_schema_v1`, `test_open_substrate_with_unknown_version_refuses`, `test_open_substrate_with_compatible_old_version_works`, `test_substrate_close_releases_connection`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `schema.sql` со всеми таблицами **в одном DDL** (subject_state, continuity_events, continuity_snapshots, identity_record, identity_immutable_fields, relation_anchor_bindings, principals, schema_version). Реализовать `Substrate` class с `open(path)`, `close()`, hold-connection-as-resource. Реализовать `MigrationRegistry` со списком миграций v0→v1 (создать схему). Compatibility window: `READABLE_VERSIONS = {1}`, `WRITABLE_VERSION = 1`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): substrate v1 schema with versioned migrations`.

### Task 4: SubjectState + ContinuityStream + Snapshot

**Files:**
- Create: `src/sonya/state/subject_state.py`, `src/sonya/state/continuity_stream.py`
- Create: `tests/sonya/test_subject_state.py`, `tests/sonya/test_continuity_stream.py`

- [ ] **Step 1:** Тесты: `test_subject_state_round_trip`, `test_subject_state_restore_after_restart`, `test_continuity_stream_is_append_only`, `test_continuity_event_has_monotonic_seq`, `test_snapshot_replay_reproduces_state`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `SubjectState` (active relation principal_id, last canonical response ref, active channels list, pending intentions list — все nullable пока). Реализовать `ContinuityEvent(seq, kind, principal_id, payload, timestamp)` и `ContinuityStream` с `append`, `read_since`, `latest_seq`. Реализовать `ContinuitySnapshot.create_from(stream)` и `ContinuitySnapshot.restore_to(stream, snapshot)`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): subject_state, continuity_stream, snapshot`.

### Task 5: Identity с immutable enforcement

**Files:**
- Create: `src/sonya/state/identity.py`
- Create: `tests/sonya/test_identity_immutable.py`

- [ ] **Step 1:** Тесты: `test_identity_record_round_trip`, `test_writing_to_things_not_to_betray_via_runtime_api_raises`, `test_writing_to_things_not_to_betray_via_governed_change_succeeds`, `test_relation_anchor_binding_round_trip`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `IdentityRecord` с явным `IMMUTABLE_FIELDS = {"things_not_to_betray", "relation_anchor_bindings"}`. Класс `IdentityWriter` имеет два метода: `write_mutable(record)` (отказывает на immutable полях) и `write_via_governed_change(record, change_id, approver)` — пока stub: принимает change_id, логирует в continuity_stream как `governed_identity_change`, применяет изменение. На этой фазе **самого governed change protocol** ещё нет — есть только enforcement, что immutable нельзя писать обычным путём. Реализовать `RelationAnchorBinding(principal_id, trusted_identifiers, trust_evidence, authority_scope, channel_constraints)` как dataclass.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): identity record with immutable zone enforcement`.

### Task 6: Principal registry (minimal)

**Files:**
- Create: `src/sonya/state/principals.py`
- Create: `tests/sonya/test_principals.py`

- [ ] **Step 1:** Тесты: `test_principal_register_and_get`, `test_principal_id_is_unique`, `test_principal_resolve_by_trusted_identifier_returns_match_or_none`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `Principal(principal_id, display_name, trusted_identifiers: tuple[str, ...], authority_scope: tuple[str, ...], created_at)`. Реализовать `PrincipalRegistry` с `register`, `get(principal_id)`, `resolve_by_trusted_identifier(value)`. Никакой identity resolution из реальных каналов — только in-memory + persistent CRUD. Реальный resolution — Фаза 2.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): minimal principal registry`.

### Task 7: Async typed event bus

**Files:**
- Create: `src/sonya/runtime/__init__.py`, `src/sonya/runtime/events.py`
- Create: `tests/sonya/test_event_bus.py`

- [ ] **Step 1:** Тесты: `test_publish_to_typed_subscriber`, `test_subscriber_does_not_receive_other_event_types`, `test_async_subscribers_receive_concurrently`, `test_unsubscribe_works`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `EventBus` с `publish(event)`, `subscribe(event_type, handler)`, `unsubscribe(handle)`. Subscribers — async callable. Использовать `asyncio.create_task` для concurrent dispatch. `Event` — pydantic BaseModel с `event_type: str` и `payload: dict`. На этой фазе типов событий немного: `subject.lifecycle.started`, `subject.lifecycle.stopping`, `subject.lifecycle.stopped`, `subject.continuity.event_appended`. Bus НЕ касается substrate — это plumbing.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/runtime): typed async event bus`.

### Task 8: Write-master с advisory lock

**Files:**
- Create: `src/sonya/runtime/write_master.py`
- Create: `tests/sonya/test_write_master.py`

- [ ] **Step 1:** Тесты: `test_acquire_release_lock`, `test_second_acquire_blocks_or_fails`, `test_lock_released_on_process_exit`, `test_read_only_does_not_acquire_lock`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `WriteMaster` через комбинацию: SQLite `PRAGMA locking_mode=EXCLUSIVE` + lock-file (`sonya_substrate.lock`) с PID. `acquire()` проверяет существующий lock-file: если PID активен — `WriteMasterContention`. Если PID мёртв — забирает. `release()` чистит lock-file. Reader-режим (`Substrate.open(read_only=True)`) lock не берёт.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/runtime): write-master with sqlite advisory lock`.

### Task 9: Layer boundary test

**Files:**
- Create: `tests/sonya/test_layer_boundary.py`

- [ ] **Step 1:** Тест: `test_state_does_not_import_runtime` — пробегает по всем модулям `src/sonya/state/*` через AST и проверяет, что ни один не импортирует `sonya.runtime`. Тест: `test_runtime_only_uses_state_public_api` — проверяет, что `sonya.runtime.*` импортирует только `sonya.state.substrate` (и его публичные re-exports), а не приватные модули.
- [ ] **Step 2:** Run → FAIL (модули ещё не выставили public API).
- [ ] **Step 3:** Поправить `src/sonya/state/__init__.py` так, чтобы он явно re-export-ил `Substrate`, `SubjectState`, `ContinuityStream`, `ContinuityEvent`, `IdentityRecord`, `RelationAnchorBinding`, `Principal`, `PrincipalRegistry` и больше ничего. Все runtime-модули зовут только это.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `test(sonya): enforce state↔runtime layer boundary`.

### Task 10: Lifecycle с graceful shutdown

**Files:**
- Create: `src/sonya/runtime/lifecycle.py`
- Create: `tests/sonya/test_lifecycle.py`

- [ ] **Step 1:** Тесты: `test_lifecycle_emits_started_event`, `test_lifecycle_handles_sigterm_gracefully`, `test_lifecycle_flushes_substrate_on_stop`, `test_double_start_raises`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `Lifecycle(substrate, event_bus)`. `start()`: append `subject.lifecycle.started` в continuity stream через write-master, publish event. `request_stop()`: append `subject.lifecycle.stopping`, дать subscribers до 5 секунд завершиться, append `subject.lifecycle.stopped`, release write-master, close substrate. Signal handling — через `asyncio.add_signal_handler` для SIGTERM/SIGINT. На Windows fallback через `signal.signal`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/runtime): lifecycle with graceful shutdown and continuity events`.

### Task 11: Health file-ping

**Files:**
- Create: `src/sonya/runtime/health.py`
- Create: `tests/sonya/test_health.py`

- [ ] **Step 1:** Тесты: `test_health_writes_initial_ping_on_start`, `test_health_updates_ping_at_least_every_30s`, `test_health_includes_pid_and_version_and_uptime`, `test_health_stops_updating_after_stop`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `Health(path, interval_seconds=10)`. Async loop пишет JSON `{pid, started_at, last_ping_at, schema_version, status}` в `path` каждые `interval_seconds`. Запуск/остановка через lifecycle subscription.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/runtime): file-ping health endpoint`.

### Task 12: Composition root в main

**Files:**
- Modify: `src/sonya/main.py`

- [ ] **Step 1:** Тесты пишутся как integration: `test_main_starts_and_stops_via_signal` (использует `asyncio.create_subprocess_exec`, проверяет что `health.json` появляется и обновляется, потом отправляет SIGTERM, проверяет что `subject.lifecycle.stopped` появилось в continuity_stream).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `main()` как: load config → open substrate (refusing if version mismatch) → acquire write-master → create event_bus → create Lifecycle → create Health → start all → run forever / until signal → graceful stop. Логировать каждый шаг.
- [ ] **Step 4:** Run → PASS. Запустить `python -m sonya` руками, подождать 60 секунд, проверить `health.json`, послать SIGTERM, проверить чистое завершение.
- [ ] **Step 5:** Commit `feat(sonya): composition root, end-to-end runtime`.

### Task 13: Systemd unit + deploy README

**Files:**
- Create: `deploy/systemd/sonya.service`, `deploy/README.md`

- [ ] **Step 1:** Никакого failing-теста — это конфигурация. Smoke-проверка: на Linux/WSL `systemd-run --user --unit=sonya-test python -m sonya` должен запустить процесс и `systemctl --user status sonya-test` показать `active (running)`.
- [ ] **Step 2:** Если у нас Windows-only сейчас — пометить smoke как «manual on Linux/WSL», но юнит должен быть валидным `systemd-analyze verify`-ом.
- [ ] **Step 3:** Реализовать unit `[Service] Type=simple ExecStart=/opt/sonya/.venv/bin/python -m sonya EnvironmentFile=/opt/sonya/.env Restart=always`. README с шагами install/enable/start/logs.
- [ ] **Step 4:** Manual smoke (опционально на этой фазе).
- [ ] **Step 5:** Commit `chore(deploy): systemd unit and deploy README skeleton`.

### Task 14: Closure — обновить документы и закрыть Фазу 0

**Files:**
- Modify: `docs/GLOBAL_PROJECT_CHECKLIST.md`, `docs/ROADMAP.md`, `docs/governance/DRIFT_REVIEW.md`, этот план.

- [ ] **Step 1:** В `GLOBAL_PROJECT_CHECKLIST.md` секция «5. Runtime shell» — флипнуть пункты которые реально появились (`src/sonya/` — теперь ✅, event bus — ✅, lifecycle — ✅, health — ✅, restart-safe — ✅). Секция «1. Foundation» — флипнуть 🟡 «Doc-review gate: проверка на реальных PR» и 🟡 «Drift review cadence: подтверждение регулярности» — оба теперь имеют по живому PR.
- [ ] **Step 2:** В `ROADMAP.md` Фаза 0 закрывается полностью; Фаза 1 переходит в `Status: complete` (или соответствующий маркер).
- [ ] **Step 3:** В `governance/DRIFT_REVIEW.md` — новая запись с фактическими findings, status changes по этому плану, и follow-ups (Фаза 2 — provider/principal core).
- [ ] **Step 4:** Этот план переводится в `Status: Archived` с пойнтером на `src/sonya/` как реализацию.
- [ ] **Step 5:** Commit `docs(phase1): close Phase 0 gate, mark substrate bootstrap complete`.

## 7. Verification

Локально:

- `pytest -v` (вся тестовая база, включая существующие `tests/sonya_runtime/` и `packages/tg-bridge/tests/`) — зелёные.
- `pyright --strict src/sonya` — без ошибок.
- `python -m sonya` — запускается, держит health, переживает SIGTERM.
- `cat var/sonya/health.json` — обновляется.
- Запустить второй `python -m sonya` параллельно — должен отказать с `WriteMasterContention`.

VPS-готовность:

- `systemd-analyze verify deploy/systemd/sonya.service` — без warnings.

Регрессия:

- `pytest packages/tg-bridge/tests/` — все существующие тесты бриджа зелёные. Бридж не тронут.
- `pytest tests/sonya_runtime/` — все существующие тесты action/task slice зелёные.

## 8. Self-Review

### Spec coverage

- substrate v1 schema: Task 3
- subject_state + continuity: Task 4
- identity + immutable enforcement: Task 5
- principals (минимум): Task 6
- event bus: Task 7
- write-master: Task 8
- layer boundary enforcement: Task 9
- lifecycle: Task 10
- health: Task 11
- composition root: Task 12
- systemd: Task 13
- closure: Task 14

### Placeholder scan

- no `TODO`
- no `TBD`
- no "implement later"
- `IdentityWriter.write_via_governed_change` — это **не** placeholder, это явно объявленный stub: enforcement immutable работает, но сам governed change protocol (с участием Ивана-anchor) — пост-MVP, потому что для него нужны Provider/Principal (Фаза 2) и Subject Core (Фаза 3) сначала. Это отмечено в коде явным docstring и в `SUBSTRATE_STANCE.md §11`.

### Type consistency

- `principal_id` — везде `str`, не `int` (UUID-like).
- `seq` в continuity stream — `int`, монотонно растущий, генерируется substrate-ом, не вызывающей стороной.
- `event_type` — `str` в формате `domain.subject.action` (`subject.lifecycle.started`).
- `Path` для всех файловых путей; никаких `str` для путей.

### Doc-review gate

- [ ] Governing documents that describe the affected contract were updated, or a follow-up was explicitly recorded in the commit message
- [ ] [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md) updated if files moved or changed role — здесь не нужно, новые файлы под `src/`, а не `docs/`
- [ ] [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md) updated — Task 14
- [ ] `Last reviewed` updated on every touched governing doc — Task 14
- [ ] Subsystem-scale change recorded in [governance/DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md) — Task 14

## 9. Promotion Note

План создан как `Status: Active` (пропускаем Draft, потому что reference check уже завершён в момент создания, и план готов к исполнению). После завершения Task 14 — `Status: Archived` с пойнтером на `src/sonya/` и upcoming Phase 2 plan.
