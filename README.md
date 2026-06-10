# Sonya

Repository for Sonya core, reusable runtime packages, and active implementation work.

## Где начать (для людей и ИИ-моделей)

- **`docs/INDEX.md`** — карта документации и порядок приоритета источников.
- **`docs/ATRIUM_PROJECT_PLAN.md`** — главный активный план разработки Atrium.
- **`docs/HANDOFF.md`** — текущая точка продолжения и результаты последних проверок.
- **`docs/MASTER.md`** — governing doc, полная картина: что строим, путь до AGI, что делать.
- `docs/core/*` — identity-critical инварианты (governed-change-only).
- `docs/atrium/PLAN.md` — исторический Atrium roadmap; не источник текущего состояния.

## Тесты

```powershell
.venv\Scripts\python -m pytest tests/sonya -q --tb=short --ignore=tests/sonya/test_main_seeds_identity.py --deselect tests/sonya/test_memory_recall.py::test_recall_round_trip --deselect tests/sonya/test_internal_loop.py::test_tick_count_increments
```

## Deploy

```powershell
git pull --rebase origin develop
git push origin develop
ssh jester-sonya@34.38.255.149 "bash ~/Sonya/deploy/update.sh 2>&1 | tail -15"
```
