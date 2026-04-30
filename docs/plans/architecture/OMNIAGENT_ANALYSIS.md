# OMNIAGENT ANALYSIS

## 1. Что такое OmniAgent для проекта

OmniAgent - это сторонний framework с сильным marketing surface:

- OmniEvolve;
- Hyper-Harness;
- Deep Reflexion;
- proactive memory;
- realtime skill evolution;
- context evolution;
- brainmodel evolution.

Для проекта Сони это важно не потому, что OmniAgent является хорошей базой, а потому что он:

- использует близкий vocabulary;
- пытается закрыть похожие классы задач;
- показывает, где красивые claims расходятся с реальной кодовой базой.

## 2. Что в OmniAgent полезного

### 2.1 Vocabulary and module taxonomy

OmniAgent полезен как словарь модулей:

- evolution layers;
- harness;
- reflexion;
- multi-agent supervision;
- context/memory framing.

### 2.2 Security as multi-layer concern

Даже если реализация там сырая, сама идея того, что safety не сводится к одному флагу, правильная.

### 2.3 Attempt at explicit orchestration

В отличие от простых agent wrappers, OmniAgent хотя бы пытается мыслить:

- planning agents;
- safety agents;
- tool execution control;
- context layering.

Это полезно как reference direction.

## 3. Что в OmniAgent плохое как в базе

### 3.1 README inflation

README обещает больше, чем кодовая база надёжно подтверждает.

Это плохо для проекта Сони, потому что здесь нельзя строить ядро на wishful marketing.

### 3.2 Security trust gap

По прошлому аудиту было видно, что gateway/auth surface and approval logic не тянут уровень доверия, который нужен для Sonya core.

### 3.3 Channel claims vs runtime truth

Заявленные channels не равны гарантированно рабочим and hardened channels.

### 3.4 Alpha-codebase risk

OmniAgent выглядит как сырая база с хорошими амбициями, а не как надёжный фундамент.

## 4. Что берём из OmniAgent

- naming and module decomposition hints;
- ambition to separate evolution dimensions;
- idea that harness and reflexion are first-class;
- warning that these concepts are easy to overclaim and underbuild.

## 5. Что не берём

- кодовую базу как foundation;
- security claims on trust;
- README promises as architecture truth;
- assumption that "channel exists in README" means "channel is production-ready".

## 6. Роль OmniAgent в Sonya project

OmniAgent должен играть роль:

- concept reference;
- anti-pattern source;
- vocabulary donor.

Но не роль:

- runtime foundation;
- trusted secure shell;
- direct base for Sonya MVP.

## 7. Итоговый вывод

OmniAgent полезен как проект, с которым стоит спорить и из которого стоит вытаскивать язык и идеи.

Но строить Соню поверх него как поверх готового базиса было бы ошибкой.

Соня должна не "пересесть на OmniAgent", а использовать отдельные идеи OmniAgent inside a cleaner architecture with stricter identity, memory, harness and principal logic.
