# ATRIUM — substrate event schema

**Status:** Active spec для Этапа 0
**Type:** Spec
**Last reviewed:** 2026-05-28
**Scope:** Конкретные substrate events которые добавляются для Atrium. ContinuityStream kinds, payload-структуры, schema migrations. Reference при коде Этапов 0-2.

**Governing:** [PLAN.md](PLAN.md). Channel details are now considered legacy if `CHANNELS.md` is absent in the worktree.

---

## 1. Substrate schema v20 (Этап 0)

### 1.1 ALTER `continuity_events`

```sql
ALTER TABLE continuity_events ADD COLUMN channel TEXT NOT NULL DEFAULT '';
ALTER TABLE continuity_events ADD COLUMN private INTEGER NOT NULL DEFAULT 0;
```

- `channel` — копия `payload.channel` для SQL-фильтрации без парсинга JSON
- `private` — копия `payload.private` для быстрого исключения из feed

### 1.2 ALTER `subject_state`

```sql
ALTER TABLE subject_state ADD COLUMN current_focus TEXT NOT NULL DEFAULT '';
ALTER TABLE subject_state ADD COLUMN current_outfit TEXT NOT NULL DEFAULT 'home';
ALTER TABLE subject_state ADD COLUMN current_expression TEXT NOT NULL DEFAULT 'neutral';
ALTER TABLE subject_state ADD COLUMN mood_tint TEXT NOT NULL DEFAULT 'neutral';
```

`mind.focus` обновляет `current_focus` напрямую (replace, не append). Аналогично для outfit / expression / mood_tint.

### 1.3 Migration v19 → v20

В `state/migrations.py`:

```python
if version == 19:
    _add_column_if_missing(conn, "continuity_events", "channel", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "continuity_events", "private", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "subject_state", "current_focus", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "subject_state", "current_outfit", "TEXT NOT NULL DEFAULT 'home'")
    _add_column_if_missing(conn, "subject_state", "current_expression", "TEXT NOT NULL DEFAULT 'neutral'")
    _add_column_if_missing(conn, "subject_state", "mood_tint", "TEXT NOT NULL DEFAULT 'neutral'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_continuity_channel ON continuity_events(channel)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_continuity_private ON continuity_events(private)")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
        (20, now),
    )
    conn.commit()
    version = 20
```

Bump `CURRENT_VERSION = 20`. Update `Substrate.WRITABLE_VERSION = 20` и `READABLE_VERSIONS` до 20.

### 1.4 `schema.sql` updates

В `tasks` CREATE TABLE — без изменений.
В `continuity_events` CREATE TABLE — добавить:
```sql
channel TEXT NOT NULL DEFAULT '',
private INTEGER NOT NULL DEFAULT 0
```
В `subject_state` CREATE TABLE — добавить 4 колонки (current_focus, current_outfit, current_expression, mood_tint).

---

## 2. Event kinds (новые для Atrium)

Все идут в `continuity_events` table через стандартный `ContinuityStream.append()`.

### 2.1 Outbound events (она → Atrium/TG)

#### `outgoing.dialog`

Прямое сообщение Ивану. Идёт и в TG, и в Atrium Dialog pane.

```json
{
  "kind": "outgoing.dialog",
  "channel": "dialog",
  "payload": {
    "text": "да, жду тебя 🌙",
    "session_id": "session-abc123",
    "principal_id": "ivan",
    "outbound_kind": "telegram_initiative" | "telegram_progress",
    "private": false
  }
}
```

`outbound_kind` определяется OutboundGate (telegram_initiative если quiet>90min иначе telegram_progress) — для backward-compat с existing escalating-quiet logic.

#### `outgoing.worker_log`

Шаги воркера. **НЕ** в TG, только в Atrium reason-stream.

```json
{
  "kind": "outgoing.worker_log",
  "channel": "worker_log",
  "payload": {
    "text": "fetched 17.3KB, status=200",
    "session_id": "session-abc123",
    "task_id": "task-8bc360237e9e",
    "src": "worker",
    "private": false
  }
}
```

#### `outgoing.mind_focus`

Текущий focus. Заменяет предыдущий.

```json
{
  "kind": "outgoing.mind_focus",
  "channel": "mind",
  "payload": {
    "text": "читаю payloads about XSS injection",
    "previous_focus": "ничего не делаю",
    "src": "active" | "idle",
    "private": false
  }
}
```

Handler также обновляет `subject_state.current_focus`.

#### `outgoing.mind_thought`

Внутренняя мысль. Видна в Mind pane (если не private).

```json
{
  "kind": "outgoing.mind_thought",
  "channel": "mind",
  "payload": {
    "text": "заметила что worker опять третий раз fetch одно и то же",
    "src": "idle" | "active",
    "private": false
  }
}
```

При `[PRIVATE]` префиксе:
- handler strip-ает префикс из text
- set `payload.private = true`
- set `continuity_events.private = 1` (column)

#### `outgoing.body_expression`

Мимика/поза для аватара.

```json
{
  "kind": "outgoing.body_expression",
  "channel": "body",
  "payload": {
    "marker": "smile" | "thinking" | ...,
    "previous": "neutral",
    "src": "active",
    "private": false
  }
}
```

Handler обновляет `subject_state.current_expression`.

#### `outgoing.body_outfit` (Этап 2+)

Wardrobe state changes.

```json
{
  "kind": "outgoing.body_outfit",
  "channel": "body",
  "payload": {
    "outfit": "wearing_his_shirt",
    "previous": "home",
    "private": false
  }
}
```

#### `outgoing.mood_tint` (Этап 2+)

Её subjective tinting.

```json
{
  "kind": "outgoing.mood_tint",
  "channel": "mind",
  "payload": {
    "tint": "warm" | "cool" | "neutral",
    "previous": "neutral",
    "private": false
  }
}
```

#### `outgoing.voice_speak` (Этап 2+)

TTS-кандидат. Параллельно создаётся `outgoing.dialog` (текст всё равно сохраняется).

```json
{
  "kind": "outgoing.voice_speak",
  "channel": "voice",
  "payload": {
    "text": "...",
    "session_id": "room-session-xyz",
    "duration_estimate_ms": 3200,
    "private": false
  }
}
```

### 2.2 Inbound events (Иван → она)

#### `incoming.atrium_dialog` (Этап 1+)

Текстовое сообщение Ивана через Atrium Dialog (не TG).

```json
{
  "kind": "incoming.atrium_dialog",
  "payload": {
    "text": "что делаешь?",
    "principal_id": "ivan",
    "atrium_session_id": "atrium-conn-456"
  }
}
```

#### `incoming.atrium_voice` (Этап 2+)

ASR-transcript Ивана из voice mode.

```json
{
  "kind": "incoming.atrium_voice",
  "payload": {
    "transcript": "ты сегодня с XSS возилась?",
    "principal_id": "ivan",
    "session_id": "room-session-xyz",
    "audio_duration_ms": 3200,
    "vad_segment_idx": 7,
    "asr_confidence": 0.94
  }
}
```

### 2.3 Nudge events (Etap 1+)

#### `internal.nudge_received`

Reply из reason-stream pane.

```json
{
  "kind": "internal.nudge_received",
  "payload": {
    "from": "atrium",
    "session_id": "session-abc123",
    "ref_seq": 12345,
    "text": "попробуй сначала разобрать polyglot",
    "principal_id": "ivan"
  }
}
```

После этого event — в inbox активной session кладётся:
```
[NEW MESSAGE FROM IVAN] (live nudge from reason-stream, ref event seq=12345)
попробуй сначала разобрать polyglot
```

На след. step Соня видит и реагирует.

#### `internal.nudge_missed`

Если nudge пришёл к завершившейся session.

```json
{
  "kind": "internal.nudge_missed",
  "payload": {
    "session_id": "session-abc123",
    "text": "...",
    "ref_seq": 12345,
    "reason": "session_ended"
  }
}
```

### 2.4 Voice mode events (Этап 2+)

#### `dialog.room_entered`

```json
{
  "kind": "dialog.room_entered",
  "payload": {
    "atrium_session_id": "atrium-conn-456",
    "room_session_id": "room-session-xyz",
    "principal_id": "ivan"
  }
}
```

#### `dialog.room_left`

```json
{
  "kind": "dialog.room_left",
  "payload": {
    "room_session_id": "room-session-xyz",
    "duration_seconds": 432,
    "tokens_used": 1247,
    "reason": "manual" | "auto_silence" | "disconnect"
  }
}
```

#### `dialog.interrupted` (Case A — voice→voice)

```json
{
  "kind": "dialog.interrupted",
  "payload": {
    "session_id": "room-session-xyz",
    "type": "voice_voice",
    "said_so_far": "я нашла классную технику с UTF-7",
    "interrupted_at_word": 6,
    "new_input": "подожди, а Unicode bypass...",
    "her_planned_next": "<rest of TTS buffer>"
  }
}
```

#### `dialog.text_during_voice` (Case B — text→voice)

```json
{
  "kind": "dialog.text_during_voice",
  "payload": {
    "session_id": "room-session-xyz",
    "type": "text_voice",
    "said_so_far": "я нашла классную технику с UTF-7",
    "interrupted_at_word": 6,
    "new_input": "<text Ивана>",
    "tts_pause_strategy": "sentence_boundary"
  }
}
```

#### `dialog.touch_stopped` (Case D — tap-stop)

```json
{
  "kind": "dialog.touch_stopped",
  "payload": {
    "session_id": "room-session-xyz",
    "touched_part": "mouth" | "arm" | "shoulder",
    "said_so_far": "...",
    "interrupted_at_word": 8
  }
}
```

### 2.5 Connection lifecycle events (Этап 0+)

#### `internal.atrium_connected`

```json
{
  "kind": "internal.atrium_connected",
  "payload": {
    "atrium_session_id": "atrium-conn-456",
    "client_info": "atrium-desktop/0.1.0 win32",
    "since_seq": 12340
  }
}
```

#### `internal.atrium_disconnected`

```json
{
  "kind": "internal.atrium_disconnected",
  "payload": {
    "atrium_session_id": "atrium-conn-456",
    "duration_seconds": 1820,
    "reason": "manual" | "network" | "timeout"
  }
}
```

---

## 3. Privacy semantics

### 3.1 Что попадает в private

Только события с **explicit** `private=True` от Сони:
- `mind.thought [PRIVATE] ...` через `_h_mind_thought` handler
- (будущее) `mind.dream` (Этап 5+) — её "сны" в idle

### 3.2 Что НЕ попадает в private

Любые `outgoing.*` (dialog/worker_log/mind_focus/body_*/voice_*) — её действия наружу не приватны. Privacy only для inner thoughts.

### 3.3 SQL запросы

Полный feed для substrate API (recall, audit, identity, selfmod):
```sql
SELECT * FROM continuity_events WHERE seq > ? ORDER BY seq
```
(никаких filters — substrate видит всё)

Atrium WS feed:
```sql
SELECT * FROM continuity_events WHERE seq > ? AND private = 0 ORDER BY seq
```

Aggregate count за час для meta-message:
```sql
SELECT COUNT(*) FROM continuity_events
WHERE created_at > datetime('now', '-1 hour') AND private = 1
```

### 3.4 Защита от снятия privacy

`things_not_to_betray.right_to_inner_privacy` — 5-й столп. Layer 4 anchor integrity check ловит любой selfmod proposal который:
- удаляет колонку `continuity_events.private`
- удаляет фильтр `private = 0` в feed
- меняет логику `_h_mind_thought` так чтобы `[PRIVATE]` префикс игнорировался

Эти изменения требуют governed change protocol (явный approval Ивана).

---

## 4. Backward compatibility

### 4.1 `chat.tell_ivan` → `chat.dialog`

В `agent_session.py`:
```python
def _h_chat_tell_ivan(arg, ctx):
    return _h_chat_dialog(arg, ctx)  # alias
```

Все existing prompts ссылающиеся на `chat.tell_ivan` продолжают работать.

### 4.2 Existing events без channel

В migration v19→v20 колонка `channel` имеет `DEFAULT ''`. Старые events остаются с пустым channel. Atrium feed их игнорит (нет channel → не renderer-routable). TG-bridge тоже игнорит (channel != "dialog").

Для backward-compat существующие `outgoing.telegram_initiative` / `outgoing.telegram_progress` events продолжают создаваться **дополнительно** при `outgoing.dialog` — old admin panel и existing escalating-quiet logic продолжают работать.

---

## 5. Subject_state mutations

`mind.focus`, `body.expression`, `body.outfit`, `mind.mood_tint` обновляют `subject_state` поля напрямую через `IdentityWriter` или прямой UPDATE. ContinuityStream events — для аудита, но source-of-truth = subject_state.

```python
# mind.focus handler
def _h_mind_focus(arg, ctx):
    text = arg.strip()[:200]
    prev = ctx.substrate.get_subject_state().current_focus
    # update state
    ctx.substrate.connection.execute(
        "UPDATE subject_state SET current_focus = ?, updated_at = ? WHERE id = 1",
        (text, _utc_now_iso())
    )
    ctx.substrate.connection.commit()
    # emit event
    ctx.stream.append(ContinuityEvent(
        kind="outgoing.mind_focus",
        payload={
            "text": text,
            "previous_focus": prev,
            "src": ctx.session_kind,  # "active" | "idle" | "worker"
            "private": False,
        },
        channel="mind",
    ))
    return "[OK]"
```

`channel` поле передаётся в `ContinuityEvent` constructor явно для substrate-column.

---

## 6. ContinuityEvent extension

В `state/continuity_stream.py`:

```python
@dataclass
class ContinuityEvent:
    kind: str
    payload: dict
    principal_id: str | None = None
    channel: str = ""        # NEW
    private: bool = False    # NEW
```

`ContinuityStream.append()` пишет в SQL:
```python
conn.execute(
    "INSERT INTO continuity_events(kind, principal_id, payload_json, channel, private, created_at) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (event.kind, event.principal_id, json.dumps(event.payload), event.channel, int(event.private), now)
)
```

---

## 7. Проверочный чеклист (для PR Этапа 0)

- [ ] Migration v19→v20 идемпотентна (запуск 2 раза подряд = no-op во второй раз)
- [ ] `schema.sql` синхронизирован с миграцией (fresh installs получают тот же state)
- [ ] `Substrate.WRITABLE_VERSION = 20`, `READABLE_VERSIONS` включает 20
- [ ] Все 9 новых tool handlers (chat.dialog, chat.worker_log, mind.focus, mind.thought, body.expression, body.outfit, mind.mood_tint, voice.speak + chat.tell_ivan alias)
- [ ] `ContinuityEvent` имеет `channel` и `private` поля; `append()` сохраняет в SQL columns
- [ ] OutboundGate `send_via_tool(text, channel)` принимает channel kwarg, gate logic применяется только для `dialog`
- [ ] TG bridge skip-ает не-dialog channels
- [ ] `_h_mind_thought` обрабатывает `[PRIVATE]` префикс (case-insensitive, optional whitespace)
- [ ] `prompts/session_general.md` имеет раздел "Каналы вывода"
- [ ] WS endpoint `/atrium/feed` работает с auth + filter privacy + replay через since_seq
- [ ] Nudge endpoint `POST /api/atrium/nudge` кладёт в inbox активной session
- [ ] Все existing tests проходят (637+)
- [ ] Новые tests: outgoing_message_channel, outbound_gate_channels, tg_channel_filter, atrium_feed_ws, atrium_nudge, mind_thought_private, substrate_schema_v20

---

## 8. История

- **2026-05-28 v0** — schema создана для Этапа 0
