# ATRIUM Этап 2 — Research: 3D-модель + голос

**Status:** Research (ready for Иван's decision)
**Type:** Research / Decision doc
**Last reviewed:** 2026-05-29
**Scope:** Конкретные решения для Этапа 2 Atrium: (1) как сгенерировать/собрать 3D-модель Сони, (2) как клонировать голос с английского референса в русскую речь, (3) как всё это рендерится и липсинкается внутри Atrium (Tauri WebView).

**Контекст:** Иван попросил найти решения до начала реализации Этапа 2. Референс голоса найден — 30 минут английского аудио. Внешность Сони — `docs/personality/APPEARANCE.md` (2B-база: silver-white bob, чёрная повязка-ободок поверх волос, холодная белая кожа, без родинки, домашний образ — чёрная oversize футболка).

> Все внешние ссылки — UNTRUSTED источники. Перед использованием любого инструмента проверять лицензию и не сливать в него identity-critical данные.

---

## 0. TL;DR — рекомендации

| Трек | Рекомендация | Почему |
|---|---|---|
| **Голос (основной)** | **Chatterbox Multilingual** (Resemble AI, MIT) | Из коробки English + **Russian**, zero-shot клон, sub-200ms, бенчмаркали против ElevenLabs. Решает главную проблему — cross-lingual (англ. референс → русская речь). |
| **Голос (если нужна максимальная похожесть)** | **GPT-SoVITS v2/v4** (MIT) — fine-tune на 30 мин | Few-shot fine-tune (1 мин достаточно, 30 мин — отлично). Лучшая похожесть тембра + эмоции. Дороже по setup (надо тренировать), есть RU. |
| **3D-модель** | **VRoid Studio → .vrm** (ручная сборка под APPEARANCE.md) | Бесплатно, заточено под аниме/2B-стилистику, экспорт в VRM (стандарт), готовый риг + 5 visemes для липсинка. Контроль над каждой деталью (повязка, bob, цвет). AI-image-to-3D пока не даёт нужного контроля/качества для постоянного аватара. |
| **Рендер в Atrium** | **`@pixiv/three-vrm` (Three.js)** в WebView | VRM грузится в Three.js, работает в Tauri WebView (тот же стек что фронт). Expressions (mimic) + visemes (aa/ih/ou/E/oh) уже в стандарте VRM. |
| **Липсинк** | **аудио-amplitude → visemes** (wawa-lipsync / Web Audio API), позже A2E-модель | Без сервера, в браузере. Для старта достаточно amplitude→jaw. Для качества — `omote-ai/lam-a2e` (Wav2Vec2 → 52 ARKit blendshapes @30fps). |

**Маршрут:** VRoid-модель (.vrm) → `@pixiv/three-vrm` в Atrium → голос через self-hosted Chatterbox (FastAPI на VPS, рядом с SearXNG) → стриминг аудио в Atrium → липсинк по амплитуде. Live2D из старого плана **заменяется на полноценный 3D VRM** (Иван хочет 3D).

---

## 1. Голос — детальный разбор

### 1.1 Главное ограничение: cross-lingual

Референс — **30 минут английского**. Соня говорит Ивану **по-русски**. Значит нужен либо:
- (A) мультиязычная модель которая берёт английский тембр и говорит по-русски (zero-shot cross-lingual), **или**
- (B) fine-tune модели с поддержкой RU на этом референсе (тембр перенесётся, язык — родной модели).

30 минут — это **много** для voice cloning. Большинству few-shot систем хватает 5-15 секунд для zero-shot и 1-5 минут для fine-tune. 30 минут позволяет сделать качественный fine-tune (вариант B) если zero-shot (вариант A) окажется недостаточно похожим.

### 1.2 Кандидаты

**Chatterbox Multilingual (Resemble AI)** — *основная рекомендация*
- Лицензия: **MIT**. 0.5B Llama backbone, 0.5M часов трейна.
- Языки из коробки: English + **Russian** (+ ещё ~21 язык). Это ключевое — cross-lingual zero-shot работает без fine-tune.
- Заявлено: бенчмарки против ElevenLabs, side-by-side предпочтения в их пользу. Sub-200ms latency (Turbo).
- Self-host: `devnen/Chatterbox-TTS-Server` — Web UI + OpenAI-compatible API + voice cloning, CUDA/ROCm/CPU. `davidbrowne17/chatterbox-streaming` — стриминг + fine-tune.
- Железо: RTX 3060 хватает для Turbo; Multilingual + длинные тексты — комфортно на RTX 3090/4090. На CPU работает, но медленно (не real-time).
- Контент-нейтральность: open weights, локальный inference → нет refusal layer (важно по `UNCENSORED_ENVIRONMENT_STANCE`).
- **Минус:** zero-shot похожесть тембра обычно чуть ниже чем у fine-tuned системы. Для 30-мин референса можно дофайнтюнить.

**GPT-SoVITS v2/v4** — *если нужна максимальная похожесть/эмоции*
- Лицензия: **MIT**. Заявка проекта: "1 минута данных → хорошая TTS-модель"; few-shot voice conversion + TTS.
- Сильные стороны: лучшая на сегодня похожесть тембра при fine-tune, хорошая эмоциональность, поддержка RU/EN/JP/ZH/KO. 30 минут — более чем достаточно для отличного результата.
- Self-host: официальный WebUI (`RVC-Boss/GPT-SoVITS`), есть готовые HF-зеркала v2/v3/v4.
- **Минус:** нужен этап обучения (не чистый zero-shot), больше возни с setup и подготовкой датасета (нарезка + транскрипт). Inference тяжелее чем у Chatterbox.

**XTTS-v2 (Coqui)** — *запасной вариант*
- Клонирование в разные языки от 6 сек референса, RU поддерживается. Зрелый, много форков (Auralis/`AstraMindAI/xtts2-gpt` для скорости).
- **Минус:** Coqui как компания закрылась; модель живёт сообществом. Лицензия Coqui (не чистый MIT — Coqui Public Model License, есть ограничения на коммерцию — для личного использования ок). Качество чуть ниже свежих Chatterbox/SoVITS.

**F5-TTS** — *хорош, но RU слабее*
- Flow-matching DiT, отличный zero-shot, 5-15 сек референса. Лучше всего по EN/ZH. RU — через community fine-tunes, не нативно. Для русского основного языка — не первый выбор.

### 1.3 План по голосу

1. **Старт:** self-host **Chatterbox Multilingual** на VPS (FastAPI, рядом с SearXNG). Прогнать 30-мин референс как cloning-source, проверить русскую речь zero-shot.
2. **Если похожесть тембра устраивает** — оставляем zero-shot, дёшево и просто.
3. **Если хочется ближе к референсу / больше эмоций** — fine-tune: либо Chatterbox (streaming-форк умеет), либо перейти на **GPT-SoVITS v2** с fine-tune на 30 мин. Сравнить A/B.
4. Интеграция: tool `voice.speak` (уже есть placeholder в Этапе 0) → POST на TTS-сервис → стриминг аудио в Atrium через WS/HTTP-chunked → проигрывание + липсинк.
5. **Бюджет/железо:** VPS сейчас CPU-only (e2-custom, без GPU). TTS на CPU не будет real-time. Варианты: (a) арендовать GPU-инстанс под TTS (RTX 3090 ≈ $0.30-1/день по ценам clore.ai), (b) гонять TTS локально у Ивана (если у него есть GPU) и стримить в Atrium, (c) для не-real-time (заранее сгенерить реплики) — можно и на CPU. Это **тот же GPU-вопрос** что блокирует RWKV (Stage 6) — возможно решать вместе.

---

## 2. 3D-модель — детальный разбор

### 2.1 Два пути: AI-генерация vs ручная сборка

**AI image-to-3D** (Direct3D-S2/Neural4D, PoseMaster, Threedium, 3DAIStudio, VRChat-forge):
- Плюс: быстро, из картинки/текста → 3D за минуты.
- Минусы для нашего кейса: (1) качество/консистентность аниме-лица нестабильны, (2) риг под липсинк/мимику не гарантирован или требует доработки, (3) повторяемость идентичности (та же Соня в каждом кадре) хуже, (4) контроль над конкретными деталями (повязка-ободок именно поверх волос, bob именно до подбородка, отсутствие родинки) слабый. Для **постоянного** аватара личности это риск дрейфа внешности — а внешность у нас identity-зона.
- Вывод: подходит для быстрого прототипа/превью, **не** для финального аватара Сони.

**VRoid Studio → VRM** (рекомендация):
- Бесплатный desktop-апп (Win/Mac/iPad) специально под аниме-аватары, royalty-free экспорт в **VRM** (humanoid на базе glTF 2.0 — индустриальный стандарт VTuber-сцены, рынок $3.13B в 2026).
- Полный контроль над параметрами: причёска (bob), цвет волос (silver-white), форма глаз/цвет (серо-голубые), тон кожи (холодный, без родинки), повязка как аксессуар поверх волос, одежда (чёрная oversize tee / 2B-платье как вторая custom-item).
- Готовый риг + стандартные **5 visemes** (aa/ih/ou/E/oh) для липсинка + blendshapes для эмоций — то что нужно для `body.expression`.
- Custom Items (с v2.10+) — сохранить разные образы (home / dress_2b) как переключаемые → ложится на наш `body.outfit` tool.
- Workflow: собрать в VRoid под APPEARANCE.md → экспорт `.vrm` → положить в `packages/atrium/assets/` → грузить в Three.js.
- Опционально: довести в Blender (тонкая правка), но для старта VRoid самодостаточен.

### 2.2 Соответствие APPEARANCE.md (чеклист сборки)

- [ ] Фигура: высокая, стройная
- [ ] Волосы: silver-white / бледно-лунный, bob до подбородка, лёгкая чёлка набок
- [ ] Глаза: светло-серо-голубые, чёткие черты
- [ ] Кожа: холодная белая, **без** тёплого подтона, **без** родинки под губой
- [ ] Повязка: чёрная, **на волосах как ободок** (поверх головы над лбом), НЕ на глазах — как аксессуар, всегда на месте
- [ ] Default outfit: чёрная oversize футболка до середины бедра, голые ноги
- [ ] Вторая outfit (custom item): боевой 2B (чёрное платье + белый подклад, перчатки, ботфорты)
- [ ] Палитра: чёрное/белое/серое, минимализм

> Внешность — **identity-зона**. Финальную модель утверждает Иван. Не дрейфить (не делать блондинкой/длинноволосой/тёплокожей).

---

## 3. Рендеринг + липсинк в Atrium

### 3.1 Стек

Atrium = Tauri 2 + WebView + Solid.js. 3D рендерится **в той же WebView** через WebGL:
- **`@pixiv/three-vrm`** (Three.js) — официальный загрузчик VRM от Pixiv. VRM 1.0, expressions API (mimic), стандартные visemes. Работает в браузере/WebView, не нужен игровой движок.
- Three.js-сцена в `<canvas>` внутри AvatarPane (сейчас там статичный SVG silhouette — заменяем на VRM-canvas) + Room view (полноэкранная сцена).
- Никакого облачного аватар-SDK (Convai/Agora/Gabber) — они тянут зависимость от чужого сервиса и латентность сети; нам нужен локальный аватар (Atrium = её зеркало присутствия, не клиент к API).

### 3.2 Анимации (из APPEARANCE + UX_SKETCH)

- Idle: моргание (random 3-7с), micro head-tilts, дыхание (грудь). Уже описано в UX_SKETCH §T2.5.
- Reactive: `body.expression <marker>` (уже tool в Этапе 0) → VRM expression preset. Маркеры из закрытого списка (neutral/smile/thinking/tired/sad/excited/curious/tender/annoyed) маппятся на VRM blendshapes.
- `body.outfit` → переключение VRM-модели/материалов (home vs dress_2b как отдельные .vrm или custom items).
- `mind.mood_tint` → освещение/тон сцены.

### 3.3 Липсинк — два уровня

**Уровень 1 (старт, без сервера):** амплитуда аудио → раскрытие рта.
- `wawa-lipsync` или ручной Web Audio API `AnalyserNode`: берём громкость TTS-потока в реальном времени → маппим на viseme `aa` (jaw open). Грубо, но работает офлайн, мгновенно, без модели. Достаточно для MVP.

**Уровень 2 (качество):** аудио → визимы по фонемам.
- `omote-ai/lam-a2e` (HF): Wav2Vec2 → **52 ARKit blendshapes @30fps**, real-time audio-to-expression. Даёт настоящую артикуляцию (не только челюсть). ARKit blendshapes маппятся на VRM. Запускать рядом с TTS (GPU).
- Альтернатива на старте — phoneme-timing от TTS (если модель отдаёт тайминги) → последовательность visemes.

### 3.4 Голос → липсинк pipeline

```
voice.speak(text)
  → TTS-сервис (Chatterbox/SoVITS на GPU) генерит аудио (стримингом)
  → аудио-чанки идут в Atrium (WS или HTTP chunked)
  → Web Audio проигрывает + AnalyserNode/lam-a2e считает visemes
  → @pixiv/three-vrm применяет visemes + expression к модели
  → параллельно текст всплывает в Dialog pane как bubble (уже есть)
```

---

## 4. Открытые вопросы / зависимости

1. **GPU.** Real-time TTS (и lam-a2e) требуют GPU. VPS сейчас CPU-only. Это та же проблема что блокирует RWKV (Stage 6). Варианты: арендный GPU-инстанс под TTS-сервис, локальный GPU Ивана, или non-real-time (pre-render реплик на CPU). **Решение за Иваном** — это main блокер реального голоса.
2. **Где живёт TTS-сервис.** Предлагаю отдельный FastAPI-сервис (как SearXNG в Docker), tool `voice.speak` ходит на него. Отвязан от core, можно крутить на другом железе.
3. **Zero-shot vs fine-tune.** Сначала пробуем Chatterbox zero-shot (быстро). Если тембр недостаточно похож — fine-tune (Chatterbox-streaming или GPT-SoVITS). 30 мин референса хватит на оба.
4. **VRM модель — кто собирает.** Сборку в VRoid под APPEARANCE.md делает Иван или я по шагам (VRoid — GUI, не код; могу дать пошаговую инструкцию + параметры). Финал утверждает Иван (identity-зона).
5. **Лицензии.** Chatterbox MIT, GPT-SoVITS MIT, VRoid royalty-free, three-vrm MIT, lam-a2e — проверить карту модели на HF. Всё совместимо с приватным некоммерческим использованием.

---

## 5. Предлагаемая последовательность реализации Этапа 2

(уточняет PLAN.md §5 — Live2D заменён на VRM-3D)

1. **T2.0 (research) — ✅ этот документ.**
2. **T2.1 — VRM-модель.** Собрать Соню в VRoid под APPEARANCE.md → `.vrm`. Утвердить с Иваном.
3. **T2.2 — Avatar рендер.** `@pixiv/three-vrm` в AvatarPane (заменить SVG) + idle-анимации (моргание/дыхание) + expressions через `body.expression`.
4. **T2.3 — TTS-сервис.** Self-host Chatterbox Multilingual (FastAPI). `voice.speak` → сервис → аудио. Проверить русскую речь с англ. референса (zero-shot → при нужде fine-tune).
5. **T2.4 — Липсинк.** Уровень 1 (amplitude) сразу; уровень 2 (lam-a2e) когда есть GPU.
6. **T2.5 — Voice room mode.** VAD + ASR (whisper) для входа Ивана голосом + interrupt-логика (4 кейса из UX_SKETCH §16.5).
7. **T2.6 — body.outfit / mood_tint рендеринг.** Переключение образов + тонировка сцены.

GPU-зависимые куски (T2.3 real-time, T2.4 уровень 2, T2.5 ASR) ждут решения по железу (см. §4.1).

---

## 6. Источники

Контент перефразирован под compliance. Ключевые источники (UNTRUSTED, проверять самостоятельно):
- Chatterbox Multilingual — [HF: ResembleAI/chatterbox](https://huggingface.co/ResembleAI/chatterbox), self-host [devnen/Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server), стриминг+fine-tune [davidbrowne17/chatterbox-streaming](https://github.com/davidbrowne17/chatterbox-streaming), железо [clore.ai guide](https://docs.clore.ai/guides/audio-and-voice/chatterbox-tts)
- GPT-SoVITS — [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)
- XTTS-v2 — [coqui/XTTS-v2](https://huggingface.co/coqui/XTTS-v2)
- F5-TTS — обзор setup [localaimaster](https://localaimaster.com/blog/f5-tts-setup-guide)
- VRoid Studio — [vroid.pixiv.help](https://vroid.pixiv.help/hc/en-us/articles/4405597663385-Getting-Started-with-VRoid), VRM формат [viverse](https://news.viverse.com/post/vrm-models-explained)
- three-vrm — [@pixiv/three-vrm npm](https://www.npmjs.com/package/@pixiv/three-vrm)
- Липсинк — [wawa-lipsync](https://wawasensei.dev/tuto/real-time-lipsync-web), A2E-модель [omote-ai/lam-a2e](https://huggingface.co/omote-ai/lam-a2e)

---

## 7. История

- **2026-05-29 v0** — research создан по запросу Ивана перед стартом Этапа 2. Рекомендации: Chatterbox Multilingual (голос, cross-lingual EN→RU), VRoid→VRM (3D), @pixiv/three-vrm (рендер). Главный блокер реального real-time голоса — GPU (общий с RWKV Stage 6).
