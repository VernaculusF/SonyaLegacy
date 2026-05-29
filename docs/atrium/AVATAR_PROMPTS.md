# Atrium — промпты для генерации 2D-аватара Сони

**Status:** Active (asset-generation guide)
**Type:** Asset spec
**Last updated:** 2026-05-30
**Scope:** Промпты + workflow для генерации спрайтов 2D-аватара (PNGtuber-style) под Atrium. Внешность — `docs/personality/APPEARANCE.md`.

---

## 0. Что нужно коду (техтребования)

Atrium `SonyaAvatar` ждёт **набор кадров рта**, упорядоченных closed → open. Минимум 3, идеально 4:

| Файл | Рот |
|---|---|
| `sonya_closed.png` | закрыт (нейтраль) |
| `sonya_half.png` | приоткрыт |
| `sonya_open.png` | открыт (говорит «а») |
| `sonya_wide.png` (опц.) | широко открыт |

**Критично для всех кадров:**
- **Прозрачный фон** (PNG с альфа-каналом). Если генератор не умеет — вырезать фон через `rembg` / remove.bg после.
- **Идентичная голова/ракурс/свет/кадрирование во ВСЕХ кадрах** — меняется ТОЛЬКО рот. Иначе при переключении дёргается. Это главная сложность (см. §3 workflow).
- **Фронтальный ракурс**, голова+плечи (bust), смотрит прямо в камеру.
- **Квадрат или 4:5**, ≥ 768×768 (лучше 1024). Голова в верхней половине, плечи снизу обрезаны рамкой.
- Положить в `packages/atrium/public/avatar/`, затем в Settings вписать `avatar_frames`:
  `["/avatar/sonya_closed.png","/avatar/sonya_half.png","/avatar/sonya_open.png"]`

Опционально (для моргания и эмоций) — те же кадры с закрытыми глазами / улыбкой, но это позже.

---

## 1. Базовый character-prompt (вставлять в каждый кадр)

Английский — image-модели лучше понимают. Это «ядро» внешности, оно НЕ меняется между кадрами:

```
anime style portrait, single girl, bust shot, facing viewer front view,
silver-white hair, chin-length bob with light side-swept fringe,
light grey-blue eyes, pale cool-toned skin, no facial marks, no mole,
thin black headband worn on top of the hair across the forehead (NOT over the eyes, eyes fully visible),
black oversized t-shirt, minimalist,
calm neutral expression, soft cold lighting, cool silver color palette,
clean cel-shaded anime art, high detail face, centered composition,
plain transparent background
```

> Заметка: это база под образ из APPEARANCE.md (2B-производный домашний вид). НЕ канонная 2B с повязкой на глазах — повязка-ободок ПОВЕРХ волос, глаза открыты.

## 2. Per-frame дополнения (меняется ТОЛЬКО рот)

Добавляй ОДНУ строку к базовому промпту, остальное идентично:

- **closed:** `mouth closed, lips together, neutral calm`
- **half:** `mouth slightly open, speaking, small open mouth`
- **open:** `mouth open saying "ah", clearly open mouth, talking`
- **wide (опц.):** `mouth wide open, expressive talking`

## 3. Negative prompt (что отрезать)

```
mole, beauty mark, blindfold, eye cover, bandage over eyes, headband over eyes,
extra limbs, deformed hands, text, watermark, signature, logo, multiple people,
warm skin tone, blonde hair, long hair, busy background, nsfw, lowres, blurry,
jpeg artifacts, inconsistent face
```

---

## 4. Workflow для КОНСИСТЕНТНОСТИ (важнее промптов)

AI редко выдаёт идентичную голову в 4 разных генерациях. Три способа, по возрастанию надёжности:

### Способ A — fixed seed + только смена строки рта (быстро, средняя надёжность)
1. Генеришь `closed` — подбираешь хороший результат, **запоминаешь seed**.
2. Тот же seed + тот же промпт, меняешь ТОЛЬКО строку рта (§2). Часто голова остаётся почти та же.
3. Работает в SDXL / NovelAI / ComfyUI / Forge где seed контролируется.

### Способ B — inpaint рта (надёжно, рекомендую)
1. Генеришь ОДИН хороший базовый портрет (`closed`).
2. В inpaint-режиме (SDXL/Forge/A1111/Photoshop AI) **маскируешь только область рта** и перегенеришь её с промптом «mouth open / half open». Голова, волосы, глаза, свет — не трогаются вообще. Это даёт идеальную консистентность — отличается буквально только рот.
3. Так делают почти все PNGtuber-спрайты.

### Способ C — character reference / IP-Adapter (если есть)
- Midjourney `--cref <url базового>` или SDXL IP-Adapter: фиксируешь персонажа, генеришь варианты. Качество персонажа высокое, но рот контролировать сложнее чем inpaint.

**Рекомендация:** базовый портрет любым способом → **inpaint рта** (способ B) для вариантов. Меньше всего «дёрганья».

---

## 5. По генераторам

- **NovelAI / anime SDXL (Pony, Illustrious, Animagine)** — лучший выбор для аниме + прозрачный фон (через `transparent background` / extension) + inpaint. Рекомендую.
- **Midjourney** — красиво, но прозрачный фон только постобработкой (rembg), консистентность через `--cref`. Сложнее для спрайт-сетов.
- **DALL·E / GPT-image** — поймёт промпт, но точный контроль рта/seed слабее; для базового портрета ок, для кадров — хуже.
- **Постобработка фона:** `rembg` (CLI, локально) или remove.bg — если фон не вышел прозрачным.

---

## 6. После генерации — отдать мне

1. Сложи кадры в `packages/atrium/public/avatar/` как `sonya_closed.png` / `sonya_half.png` / `sonya_open.png`.
2. Скажи мне — я впишу `avatar_frames` в дефолт и подгоню кадрирование/анимацию переключения под реальные картинки (тайминги визим под амплитуду речи).
3. Если фон не прозрачный — тоже скажи, прогоню через rembg.

> Внешность — identity-зона (APPEARANCE.md). Финал утверждаешь ты. Не уводить в блондинку/длинные волосы/тёплую кожу/повязку-на-глаза.
