from __future__ import annotations

from sonya_runtime.actions.planner_contract import TASK_STATUS_QUERY_MARKERS


TASK_REQUEST_MARKERS = (
    "проверь",
    "посмотри",
    "разберись",
    "подумай",
    "сделай план",
    "собери",
    "найди дыру",
    "проанализируй",
    "не мешай",
    "просто сделай",
    "вернись позже",
    "дай мне",
    "check the folder",
    "look through",
    "analyze",
    "make a plan",
)


ANTI_FAKE_AGENCY_RULES = [
    "- Do not claim you are currently checking files, scanning the workspace, creating a file, or working in the background unless the runtime actually launched that action.",
    "- Do not promise 'I will come back later' unless you return a real task action with a persisted task payload.",
    "- If the task cannot be completed in the current response and no task is created, respond with a limitation or clarification instead of simulating background work.",
    "- Bridge and channel surfaces are tools. They do not become separate Sonya instances and they do not invent fake autonomous work.",
]


def looks_like_task_request(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in TASK_REQUEST_MARKERS)


def looks_like_task_status_query(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in TASK_STATUS_QUERY_MARKERS)
