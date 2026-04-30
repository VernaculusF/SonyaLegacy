# SKILL SYSTEM PLAN

## 1. Назначение документа

Этот документ определяет, как в проекте Сони должны существовать навыки:

- как артефакты;
- как поведенческие модули;
- как объекты версионирования;
- как объекты эволюции;
- как мост между пользовательским опытом и ростом системы.

## 2. Базовый принцип

Навык в этом проекте - не просто кусок текста.

Навык - это управляемая единица поведения, которая должна иметь:

- идентичность;
- версию;
- область применения;
- trust level;
- traceability;
- lifecycle.

Если skill system сводится к prompt snippets, проект теряет один из центральных контуров роста.

## 3. Что такое skill

Skill может включать:

- инструкционную логику;
- tool-use pattern;
- context pattern;
- planning behavior;
- memory interaction behavior;
- evaluation behavior;
- self-modification proposal logic.

Skill может быть:

- purely behavioral;
- tool-centered;
- cognitive;
- operational;
- meta-skill.

## 4. Минимальная модель skill-артефакта

У каждого skill должны быть:

- `skill_id`
- `name`
- `purpose`
- `version`
- `status`
- `trust_level`
- `activation_rules`
- `dependencies`
- `allowed_tools`
- `forbidden_zones`
- `tests`
- `metrics`
- `trace_tags`
- `history`

## 5. Skill Registry

Registry должен уметь:

- хранить skills;
- выдавать активные skills;
- различать trusted and untrusted skills;
- вести версионирование;
- поддерживать deprecation and rollback.

В MVP registry обязателен.

## 6. Skill Activation

Skill activation не должна быть хаотической.

Нужно определить:

- кто активирует skill;
- в каком контексте он допустим;
- какие сигналы нужны для включения;
- какие каналы/инструменты он может использовать;
- как логируется его исполнение.

## 7. Skill Injection User Message

### 7.1 Что это

Это механизм перевода повторяющегося пользовательского паттерна в системный артефакт.

### 7.2 Что он должен делать

- находить повторяющиеся инструкции;
- определять promotable patterns;
- превращать их в skill/instruction artifact;
- выносить их из дорогого повторяющегося текста;
- сокращать токены;
- повышать устойчивость поведения.

### 7.3 Минимальный MVP

- candidate extraction;
- promotion flow;
- approval path;
- storage as skill-like artifact;
- later retrieval and activation.

## 8. Real-time Skill Evolution

### 8.1 Что это

Контур, где навыки могут:

- уточняться;
- дробиться;
- усиливаться;
- заменяться;
- архивироваться;
- откатываться.

### 8.2 Что обязательно

Даже в MVP должны существовать:

- skill improvement proposals;
- candidate revision objects;
- evaluation path;
- approval path;
- archive of accepted/rejected revisions.

### 8.3 Что не допускается

Навыки не должны менять себя silently.

Любая эволюция skill должна быть:

- traceable;
- reviewable;
- revertible;
- scoped.

## 9. Trust Levels

Навыки должны различаться по доверию.

Минимальные классы:

- `core-trusted`
- `trusted`
- `limited`
- `experimental`
- `quarantined`

Trust level влияет на:

- доступ к инструментам;
- право предлагать изменения;
- право использовать sensitive contexts;
- право участвовать в self-modification loops.

## 10. Skill Testing

У каждого важного навыка должны быть:

- usage checks;
- behavioral checks;
- tool safety checks where relevant;
- regression checks;
- anchor compatibility checks for sensitive skills.

В MVP часть тестов может быть rules-based или manual-gated, но тестовый контур обязан быть.

## 11. Skill Failure Modes

Нужно отслеживать:

- stale skills;
- over-triggering;
- conflict between skills;
- unsafe tool amplification;
- silent drift after revisions;
- prompt-bloat disguised as skill behavior;
- anchor-incompatible skills.

## 12. Skill Lifecycle

Минимальный lifecycle:

1. creation
2. review
3. activation
4. observation
5. evaluation
6. revision
7. archive or rollback

## 13. Skill System и личность Сони

Skill system не должен подменять identity layer.

Навыки - это расширения поведения.
Identity - это ядро самости.

Поэтому skill system обязан подчиняться:

- identity constraints;
- anchor constraints;
- harness rules;
- self-modification governance.

## 14. Что считается провалом

Skill system считается проваленной, если она вырождается в:

- набор prompt snippets без lifecycle;
- папку markdown без activation logic;
- хаотическое накопление skill-файлов без registry;
- самоправку без trust levels and review path;
- token-saving tricks без реального behavioral value.

## 15. Вывод

Skill system для Сони - это не украшение и не "потом добавим plugins".

Это один из центральных механизмов того, как её среда учится, стабилизируется и наращивает способности без полного переобучения всего brain stack.
