# FREEMODEL_BRIDGE.md — Доступ к флагманским моделям через freemodel.dev

**Status:** DRAFT — требует реализации
**Type:** Operational — план интеграции
**Last updated:** 2026-06-05
**Назначение:** Описание того, как подключить бесплатные флагманские модели (Opus, GPT) через freemodel.dev как дополнительные инструменты Сони.

---

## Что такое freemodel.dev

**freemodel.dev** — сервис предоставляющий доступ к флагманским моделям
(Claude Opus 4.6-4.8, Sonnet 4.6, GPT 5.4-5.5) бесплатно, с ограничениями по использованию.

### Лимиты

| Ограничение | Значение |
|-------------|----------|
| Расход за 5 часов | $10 максимум |
| Расход за 7 дней | $67 максимум |
| Счёт | **Общий** (один баланс на все модели) |

Можно создать несколько аккаунтов для увеличения квоты.

### Доступные модели (предварительно)

| Модель | Tier | Примерная стоимость за запрос |
|--------|------|------------------------------|
| Claude Opus 4.8 | Флагман | $$$ (дорогая, быстро ест лимит) |
| Claude Opus 4.7 | Флагман | $$$ |
| Claude Opus 4.6 | Флагман | $$ |
| Claude Sonnet 4.6 | Средний | $ (экономичнее) |
| GPT 5.5 | Флагман | $$$ |
| GPT 5.4 | Флагман | $$ |

### Ключевое ограничение

> **freemodel.dev работает ТОЛЬКО с официальными приложениями.**
>
> Это значит: Claude Code, Codex CLI, web-интерфейс Anthropic/OpenAI.
> Прямой OpenAI-compatible API endpoint НЕТ (или он ограничен).

### Важно: это НЕ то же самое что Codex Sale

У Ивана теперь есть **отдельный прямой провайдер `codexsale`**, который уже
даёт OpenAI-compatible endpoints без bridge:

- `https://codex.sale/v1/models`
- `https://codex.sale/v1/chat/completions`
- `https://codex.sale/v1/responses`
- `https://codex.sale/backend-api/codex`

Модели `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.5`, `gpt-image-2`,
`gpt-4o-transcribe` нужно подключать **напрямую** через keystore/provider,
а не через freemodel bridge. Этот документ остаётся только про случаи, где
мост действительно нужен — например для freemodel.dev / Claude Code / Codex CLI.

---

## Что нужно реализовать: API Bridge

Чтобы Соня могла использовать эти модели как субагентов, нужен **мост**
между freemodel.dev и OpenAI-compatible API.

### Архитектура моста

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ Соня (subagent│────▶│  Bridge Server  │────▶│  freemodel.dev   │
│  .spawn)     │     │  (localhost)     │     │  (через Claude   │
│              │◀────│                  │◀────│   Code / Codex)  │
└──────────────┘     └─────────────────┘     └──────────────────┘
```

### Вариант 1: Claude Code Bridge

Существуют решения для перенаправления API-запросов через Claude Code CLI:

1. **claude-code-proxy** — запускает Claude Code как subprocess, перехватывает
   stdin/stdout, выставляет OpenAI-compatible HTTP endpoint
2. **Настройка:**
   - Установить Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
   - Настроить авторизацию через freemodel.dev
   - Запустить proxy на localhost
   - Прописать в Сонином keystore как обычный провайдер

### Вариант 2: Codex CLI Bridge

Аналогично для OpenAI Codex CLI:

1. Установить Codex CLI
2. Настроить API endpoint на freemodel.dev
3. Proxy для OpenAI-compatible API

### Что нужно проверить

- [ ] Можно ли freemodel.dev использовать через CLI вообще (не только web)
- [ ] Какой конкретно формат авторизации (API key / OAuth / cookie)
- [ ] Существующие open-source bridge решения (GitHub search)
- [ ] Latency через bridge (добавляет overhead)
- [ ] Стабильность (freemodel.dev может менять API/лимиты)

---

## Стратегия использования лимитов

### Бюджетирование

С лимитом $10/5h и $67/7d нужно быть экономным:

| Модель | Примерная стоимость запроса (avg) | Запросов в час (approx) |
|--------|----------------------------------|------------------------|
| Opus 4.8 | ~$0.30-0.50 | ~4-6 |
| Opus 4.6 | ~$0.15-0.25 | ~8-13 |
| Sonnet 4.6 | ~$0.05-0.10 | ~20-40 |
| GPT 5.5 | ~$0.20-0.40 | ~5-10 |

### Правила для Сони

1. **НЕ использовать Opus/GPT для мелких задач** — это как стрелять из пушки по воробьям
2. **Sonnet 4.6 как default из freemodel** — баланс quality/cost
3. **Opus 4.8 / GPT 5.5 — только для задач где free OpenRouter модели НЕ справляются**
4. **Мониторить расход** — если потратили $8 из $10 за 5h, остановиться
5. **Multi-account ротация** — когда один аккаунт упёрся в лимит, переключить

### Типы задач для freemodel моделей

| Задача | Модель freemodel | Почему не OpenRouter free |
|--------|-----------------|--------------------------|
| Сложный multi-file рефакторинг | Opus 4.6+ | Нужно качество Opus |
| Identity-sensitive selfmod | Sonnet 4.6 | Нужна точность Anthropic |
| Задачи с censorship issues | Opus 4.6 (lower safety) | OpenRouter free модели могут refuse |
| Research на грани | GPT 5.5 | Лучший world knowledge |
| Critical code review | Opus 4.8 | Максимальное качество |

---

## Интеграция в систему субагентов

### Как это вписывается в SUBAGENT_MODELS.md

Модели из freemodel.dev добавляются в общий реестр как **Tier 0 — ФЛАГМАНСКИЕ**.
Соня выбирает их только когда задача действительно требует флагманского качества
И free-tier модели не справились.

Отдельно от этого, **Codex Sale** тоже даёт Tier 0 / premium-tier модели, но
без моста. То есть:

- `freemodel.dev` = bridge/proxy path
- `codexsale` = direct provider path

### Конфигурация в keystore

```
provider: freemodel-bridge
base_url: http://localhost:PORT/v1
model: claude-opus-4.8 / claude-sonnet-4.6 / gpt-5.5
slot: text
```

### Мониторинг лимитов

Bridge должен:
1. Трекать расход ($X из $10 за текущие 5h)
2. Отвечать 429 если лимит исчерпан
3. Автоматически переключать аккаунт (если настроено несколько)

---

## TODO — что делать

### Phase 1: Research (1-2 дня)
- [ ] Проверить freemodel.dev через браузер — что конкретно доступно
- [ ] Поискать существующие bridge/proxy решения на GitHub
- [ ] Проверить работу через Claude Code CLI
- [ ] Проверить работу через Codex CLI

### Phase 2: Bridge prototype (2-3 дня)
- [ ] Выбрать подход (Claude Code bridge vs Codex bridge vs custom)
- [ ] Написать минимальный прототип
- [ ] Тесты: один запрос → модель → ответ
- [ ] Мониторинг лимитов

### Phase 3: Integration (1 день)
- [ ] Добавить freemodel provider в keystore
- [ ] Обновить SUBAGENT_MODELS.md с Tier 0
- [ ] Написать budget guard для Сони
- [ ] Тесты e2e

### Phase 4: Multi-account (по необходимости)
- [ ] Создать 2-3 аккаунта freemodel.dev
- [ ] Ротация ключей при лимитах
- [ ] Мониторинг

---

## Риски

| Риск | Вероятность | Импакт | Митигация |
|------|-------------|--------|-----------|
| freemodel.dev закроется/изменит лимиты | Средняя | Высокий | Не зависеть только от него, free OR модели — основа |
| Bridge нестабилен | Высокая | Средний | Retry + fallback на OpenRouter |
| Блокировка аккаунтов | Средняя | Средний | Несколько аккаунтов, разные IP |
| Latency через bridge | Высокая | Низкий | Использовать только для фоновых задач |

---

## Changelog

- **2026-06-03** — Первая версия. Описание концепции. Требует research phase перед реализацией.
- **2026-06-05** — Добавлено явное разграничение: `codexsale` не относится к freemodel bridge и должен интегрироваться напрямую как отдельный provider с собственными GPT-моделями и спец-модальностями.
