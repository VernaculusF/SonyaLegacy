# ATRIUM — CURRENT STATE & DEVELOPMENT PLAN

**Status:** Active
**Type:** Project state + roadmap
**Last updated:** 2026-06-09
**Цель:** Atrium с полностью рабочей системой проектов, корректными ответами Сони и переработанной системой провайдеров.

---

## 1. Текущее состояние

### Что работает
- Substrate v29 с project tables, evaluation tables, workspace policy
- Project CRUD через API (`/api/projects/*`)
- Model evaluation data model (scorecards, evaluation runs, champions)
- 58 тестов проходят
- Frontend Atrium собирается (Solid/Vite)
- Базовый project policy layer (consent/forbidden/allowed)

### Что НЕ работает / не доведено
- VPS не обновлён с последними коммитами
- Система провайдеров устарела:
  - провайдер жёстко привязан к одной модели
  - нет пула моделей на провайдер
  - нет автоматического discovery
- Ответы Сони в Atrium работают плохо:
  - долгое ожидание
  - плохой парсинг tool calls
  - think/reasoning смешан с ответом
- Субагенты не интегрированы как инструменты в project context
- Project chat UX не доработан

---

## 2. Целевое состояние

### Atrium
- Один основной чат = "дом" Сони
- Проекты = рабочие пространства с отдельными чатами
- Каждый проект = папка + статус + история + traces
- Ответы Сони = быстрые, чистые:
  - raw output сразу в чат
  - reasoning/think → в скрытый блок по умолчанию
  - чистый парсинг tool calls
  - нет долгого ожидания перед первым токеном

### Субагенты
- Инструмент Сони, не отдельный субъект
- Видны в project chat как execution traces
- Пользователь только читает их переписку
- Каждый субагент одноразовый: пустой контекст + задача
- Ограниченный tool scope
- Нет доступа к общей памяти Сони

### Система провайдеров
- Провайдер = пул доступных моделей, не одна жёстко закреплённая
- Автоматический discovery моделей через `/models` endpoint
- Кэширование списка моделей
- Routing учитывает: role, cost, latency, context length, historical success

### Project statuses
- `in_progress` — работа идёт
- `waiting_choice` — нужен выбор Ивана
- `waiting` — ожидает
- `completed` — завершён
- `cancelled` — отменён

---

## 3. План работ

### Phase 1: Провайдеры и модели

**1.1 Переработать систему провайдеров**
- Убрать жёсткое закрепление `provider -> одна модель`
- Сделать `provider -> pool of models`
- Discovery моделей через `/models` endpoint провайдера
- Кэширование и обновление пула
- Health check по каждой модели отдельно

**1.2 Прописать все доступные модели**

#### OpenRouter (ключ: `ivan-main-vision`)
Модели:
- `openrouter/owl-alpha` — 1M context, медленный, reasoning
- `nex-agi/nex-n2-pro:free` — 262K, agentic MoE 17B/397B, coding/research
- `moonshotai/kimi-k2.6:free` — 262K, multimodal, agentic
- `poolside/laguna-m.1:free` — 262K, coding specialist
- `z-ai/glm-4.5-air:free` — 131K, general
- `nousresearch/hermes-3-llama-3.1-405b:free` — 128K, uncensored
- `google/gemma-4-31b-it:free` — 262K, multimodal
- `google/gemma-4-26b-a4b-it:free` — 262K, MoE 4B active, fast
- `openai/gpt-oss-120b:free` — 131K, general
- `nvidia/nemotron-3-nano-30b-a3b:free` — 256K

#### Nous Research (ключ: `sk-nous-...`)
- `nvidia/nemotron-3-ultra:free` — 1M context, coordination

#### Google AI Studio (ключ: `AQ.Ab8RN6...`)
- `gemma-4-26b` — multimodal
- `gemma-4-31b` — multimodal
- `gemini-3-flash` — 1M+ context, multimodal

#### Codex Sale (ключ: `sk-clb-...`)
- `gpt-5.3` — premium reasoning
- `gpt-5.4-mini` — premium fast
- `gpt-5.5` — premium reasoning
- `gpt-image-2` — image generation
- `gpt-4o-transcribe` — audio transcription

**1.3 Обновить SUBAGENT_MODELS.md**

### Phase 2: Ответы Сони в Atrium

**2.1 Переработать формат ответов**
- Raw output → сразу в чат
- Reasoning/think → скрытый блок (спойлер/подменю)
- Убрать лишние задержки

**2.2 Улучшить парсинг tool calls**
- Чёткое разделение tool call и текста
- Fallback парсинги для разных форматов моделей
- Retry при невалидном tool call

### Phase 3: Project workflow

**3.1 Project chat UX**
- Отдельная история сообщений на проект
- Статус проекта виден
- Subagent traces видны
- Progress indicators

**3.2 File transfer**
- Отправка файлов через Atrium
- Привязка к project context
- Chunked upload для больших файлов

### Phase 4: Deploy и тестирование

**4.1 Деплой на VPS**
- Push всех коммитов
- Проверить миграции
- Проверить API

**4.2 Первые реальные тесты**
- Создать тестовый проект
- Дать задачу через project chat
- Убедиться что ответы корректные
- Убедиться что субагенты видны как инструменты

---

## 4. Что НЕ делать

- Не превращать субагентов в отдельные чаты
- Не делать "multi-session subagent UI"
- Не прошивать жёсткие model routing rules
- Не смешивать admin с Atrium
- Не делать "smart parsing" — лучше raw output + hidden reasoning
