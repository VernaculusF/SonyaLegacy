# HANDOFF.md — текущая точка продолжения

**Status:** Active
**Type:** Session handoff
**Last updated:** 2026-06-06

---

## Где мы сейчас

Идёт переход от «Соня как discrete assistant runtime» к «Соня как рабочая среда Ивана».

Главный новый вектор:
- Atrium должен стать не только chat/UI surface, а полноценным workspace runtime
- это зафиксировано в `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`

## Что уже есть

- Substrate-based runtime с continuity, episodic и semantic memory
- active session / tg session / task progress / idle thought
- selfmod pipeline с validation и apply
- BrowserTool, providers.*, skills, knowledge.*, subagent.*
- subagent multi-model routing
- Atrium Этап 0 и Этап 1 уже есть как multichannel UI + dialog surface

## VPS и операционка

- VPS: `34.38.255.149`
- Пользователь: `jester-sonya`
- Repo на VPS: `~/Sonya`
- Substrate: `~/.sonya/sonya_substrate.db`
- Backups: `~/.sonya/backups/`
- Deploy: `bash ~/Sonya/deploy/update.sh`
- Admin: `http://34.38.255.149:8877`

Основные сервисы:
- `sonya.service`
- `sonya-admin.service`

Полезные команды:
- `journalctl -u sonya -f`
- `journalctl -u sonya-admin -f`
- `systemctl status sonya`
- `systemctl status sonya-admin`

Подробности инфраструктуры:
- `docs/operations/VPS.md`

## Что важно сейчас

### 1. Atrium больше не считать завершённым как продукт

Старый Atrium закрывает только:
- multichannel вывод
- диалог
- reason stream
- базовую наблюдаемость

Новый обязательный слой:
- project/workspace mode
- multi-workspace selection
- visible task execution
- subagent orchestration UI
- console redesign
- optional full-system access mode
- trace capture для будущего RWKV/data layer

См.:
- `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
- `docs/atrium/PLAN.md`

### 2. Tool experience memory добавлена

Соня теперь может накапливать опыт использования инструментов через:
- `tool_experiences` table
- зеркалирование в `episodic_events` как `tool_event`

Это уже используется как база для:
- telemetry/reason persistence
- model/tool learning from experience
- будущего расширения на project execution traces

### 3. Subagent path улучшен

- `codexsale` работает как direct text provider для субагентов
- есть deterministic auto-pick модели под задачу
- special-worker модели (`gpt-image-2`, `gpt-4o-transcribe`) не запускаются как text loop
- picker начинает учитывать historical experience

## Актуальные открытые задачи

### Runtime / architecture

- Atrium workspace runtime decomposition пока не сделан
- full-system-access mode пока только на уровне spec
- project entities (`project`, `workspace_binding`, `subagent_run`, и т.д.) не введены
- execution trace schema для project mode не спроектирована
- tool experience memory добавлена, но ещё не развёрнута в полноценный project telemetry layer

### Security / infra

- в Atrium нужен явный CSP
- убрать/ограничить `shell:default` capability
- перенести чувствительные операции из JS в Rust IPC handlers
- добавить auth/reconnect discipline для WS путей где ещё не доведено до нормы

### Product / UX

- REPO section неудобен и плохо показывает lifecycle selfmod/apply
- PROVIDERS section слабее админки
- SELFMOD нуждается в cleanup workflow
- TASKS нуждается в фильтрах

## Текущее состояние проекта

### Реально работает

- multichannel Atrium backend
- Atrium dialog UI и reason stream
- providers.* и BrowserTool
- selfmod pipeline с outcome tracking
- subagent auto-pick и codexsale direct text-provider path
- tool experience memory для накопления опыта использования инструментов

### Ещё не доведено до нужного состояния

- Atrium как рабочая среда для проектов
- видимое orchestration-исполнение субагентов
- полноценный provider/project console UX
- full-system-access режим
- execution traces как first-class data layer для будущего RWKV

## Если следующая сессия продолжает работу

Читать в таком порядке:
1. `docs/STATE.md`
2. `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
3. `docs/atrium/PLAN.md`
4. `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md`

## Чего не делать

- не возвращать в эти документы старый длинный session log
- не смешивать completed changelog с актуальным handoff
- не считать Atrium закрытым только потому, что dialog UI уже работает
