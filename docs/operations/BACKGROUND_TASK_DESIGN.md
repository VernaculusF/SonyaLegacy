# Background Task Design

**Status:** Active design — not yet implemented
**Last updated:** 2026-06-15
**Parent audit:** [`docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`](../SONYA_RUNTIME_COHERENCE_AUDIT.md) §9

## 1. Problem Statement

Sonya must run multiple categories of background work simultaneously. The
current architecture supports:

- Periodic ticks (internal loop scheduler)
- Finite subagent tasks (spawn → complete → event)
- Project executor (start → run → harvest)

What it does NOT support:

- **Persistent activities** — work that runs continuously (e.g., marketer
  prospecting) until explicitly stopped.
- **Strategic decision-making about priorities** — Sonya currently has no
  mechanism to decide "I should spend the next hour on marketer follow-ups
  instead of selfmod" without the decision being hardcoded by a timer.
- **Work-in-progress visibility** — Ivan cannot see what background tasks are
  active, their progress, or their results without digging through continuity
  events.

## 2. Work Category Analysis

| Category | Duration | Trigger | Example | Current support |
|---|---|---|---|---|
| Self-improvement | Periodic (daily) | Timer + drift signals | selfmod session | Partial (forced-selfmod track) |
| One-shot tasks | Finite (minutes-hours) | User request or internal decision | "find a restaurant" | Yes (subagents) |
| Project work | Finite but long (hours-days) | Project creation | build a feature | Partial (project executor) |
| Marketer | Persistent (while-true) | Explicit start command | prospect → outreach → follow-up | **No** |
| Monitoring | Persistent | Implicit | watch for inbound emails, check account health | **No** |

The fundamental tension: **persistent activities require a different execution
model than finite tasks.**

## 3. Candidate Architecture: Activity Graph

### 3.1 Core concept

Replace the implicit "timer tick + subagent spawn" model with an explicit
**Activity Graph** — a persistent, observable structure that Sonya owns and
modifies.

An **Activity** is a first-class runtime object:

```python
class Activity:
    id: str
    name: str                    # human-readable
    category: str                # "selfmod", "task", "project", "marketer", "monitor"
    mode: str                    # "periodic", "finite", "persistent"
    state: str                   # "idle", "running", "paused", "waiting_review", "stopped"
    priority: float              # 0.0-1.0, Sonya-adjustable
    schedule: str | None         # cron-like for periodic, None for persistent
    last_run: datetime | None
    next_run: datetime | None
    subagent_context: dict       # model, tools, workspace, prompt template
    result_handler: str          # what to do with results: "review", "auto_accept", "notify_ivan"
    current_phase: str | None   # e.g., "prospecting", "outreach", "follow_up"
    phase_progress: float       # 0.0-1.0 within current phase
```

### 3.2 Activity lifecycle

```
created → idle → running → waiting_review → running → ... → paused → running → ... → stopped
                 ↓
               completed (finite only)
                 ↓
               archived
```

- **Persistent activities** (mode=persistent) never reach `completed`. They
  cycle through `running → waiting_review → running` until explicitly `stopped`.
- **Periodic activities** (mode=periodic) auto-schedule their next run based
  on `schedule`. Between runs, they are `idle`.
- **Finite activities** (mode=finite) run until `completed` or `stopped`.

### 3.3 Sonya's role: strategist, not dispatcher

The key design decision: **Sonya does NOT review every subagent result.**

Instead:

1. **Auto-accept path:** For low-risk, repetitive work (marketer prospecting,
   follow-up sends), results are auto-accepted if they pass basic validation
   (no errors, within expected output schema). Sonya sees a summary, not a
   review queue.

2. **Review path:** For high-risk work (selfmod proposals, emails to new
   clients, financial decisions), results enter `waiting_review`. Sonya
   reviews these during her next cognitive tick, or they surface as a
   notification.

3. **Escalation path:** If a result is unexpected (error, unusual pattern),
   it escalates to Sonya's main attention regardless of the result handler.
   This prevents the "she becomes a dispatcher" problem while still ensuring
   she sees anomalies.

### 3.4 Scheduler integration

The internal loop scheduler picks the next activity to run based on:

1. **Priority** — Sonya adjusts priorities through selfmod or direct command.
2. **Schedule** — Periodic activities have fixed intervals.
3. **Urgency** — Escalated results or waiting reviews boost priority.
4. **Context window budget** — Don't overload Sonya's main context with
   review results from too many activities simultaneously.

The scheduler does NOT need Sonya to actively decide "what next" for every
tick. It runs automatically based on the activity graph state. Sonya only
intervenes when:
- A result enters the review path.
- She wants to adjust priorities or pause/resume an activity.
- An escalation fires.

### 3.5 Marketer activity example

```python
Activity(
    id="marketer-prospecting",
    name="Marketer: Client Prospecting",
    category="marketer",
    mode="persistent",
    state="running",
    priority=0.6,
    schedule=None,  # persistent — always runs when priority allows
    subagent_context={
        "role": "marketing_prospector",
        "model_preference": "web_proxy/cheap_worker",
        "tools": ["web.search", "web.fetch"],
        "prompt_template": "Find freelance clients for Ivan in {category}...",
    },
    result_handler="auto_accept",
    current_phase="prospecting",
    phase_progress=0.0,
)
```

When a prospector subagent completes, its results (found leads) are
auto-accepted and stored. A second activity handles outreach:

```python
Activity(
    id="marketer-outreach",
    name="Marketer: Outreach",
    category="marketer",
    mode="persistent",
    state="running",
    priority=0.5,
    subagent_context={
        "role": "marketing_outreach_writer",
        "model_preference": "web_proxy/scratch_reasoner",
        "tools": ["web.search", "web.fetch"],
        "prompt_template": "Write a personalized outreach email for {lead}...",
    },
    result_handler="review",  # emails require Sonya's review before sending
    current_phase="outreach",
    phase_progress=0.3,
)
```

## 4. Alternative Approach: Work Queue with Priority Decay

A simpler alternative: all work (including persistent activities) is modeled as
a **work queue**. Each item has a priority that decays over time if not
processed. Persistent activities generate new queue items as they cycle.

**Pros:** Simpler mental model. No new "Activity" concept — just work items
with priorities.

**Cons:** Doesn't naturally model the "while-true" pattern. Each marketer
cycle becomes a new work item, which is awkward for something that should feel
like one ongoing activity with phases.

## 5. Recommendation

Start with the **Activity Graph** (§3). It solves the core problem (persistent
activities) while preserving Sonya's role as strategist rather than dispatcher.

Implementation steps:

1. Define `Activity` model and substrate table.
2. Add activity CRUD to Sonya's tool surface (Sonya can create, pause, resume,
   stop, adjust priority).
3. Extend the internal loop scheduler to pick activities by priority and
   schedule.
4. Implement the three result paths (auto-accept, review, escalation).
5. Wire activity state changes to Atrium visibility (Ivan can see active
   activities, their phases, and results).
6. Test with selfmod as the first periodic activity, then with a simple
   persistent activity (e.g., periodic web search for a keyword).

## 6. Open Decisions

- Whether activities are stored in substrate (SQLite) or in a separate
  lightweight store (e.g., JSON file with atomic writes).
- How many subagents can run simultaneously per activity (1 by default?
  configurable?).
- Whether activities can depend on each other (e.g., marketer-outreach depends
  on marketer-prospecting having results).
- How Ivan interacts with activities from Atrium (dedicated activity pane?
  project sidebar? notification stream?).
