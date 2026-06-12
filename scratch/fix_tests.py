import re

with open(r"c:\Users\Jester\Desktop\Sonya\tests\sonya\test_agent_session_inbox_gate.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update test_grace_period_allows_early_work_tools
# It should do chat.dialog then DONE
content = re.sub(
    r'provider = _Stub\(\[\s*"\[TOOL: web.fetch https://example.com\]",\s*"\[DONE: Открыла example.com — заголовок Example Domain.\]",\s*\]\)',
    'provider = _Stub([\n        "[TOOL: web.fetch https://example.com]",\n        "[TOOL: chat.dialog]\\nОткрыла example.com — заголовок Example Domain.",\n        "[DONE]"\n    ])',
    content
)

# And remove the assertion for DONE-as-reply dispatch
content = re.sub(
    r'# DONE-as-reply dispatched\.\n    rows = substrate.connection.execute\(\n        "SELECT 1 FROM continuity_events "\n        "WHERE kind = \'internal.done_as_reply_dispatched\'"\n    \)\.fetchall\(\)\n    assert rows, "DONE-as-reply must dispatch the final body"',
    '',
    content
)

# 2. Update test_done_with_body_dispatches_as_reply_short_circuits_gate
# Rename to test_done_with_body_is_blocked_by_inbox_gate
content = content.replace(
    "test_done_with_body_dispatches_as_reply_short_circuits_gate",
    "test_done_with_body_is_blocked_by_inbox_gate"
)
content = re.sub(
    r'"""`\[DONE: <text>\]` should dispatch text as her message AND close the\s+session — bypasses both phase-1 and phase-2 gates without forcing\s+a separate chat.dialog call.\s+This makes "Иван спросил → Соня сделала → \[DONE: вот результат\]"\s+a single-shot pattern instead of two-step "ack \+ report".\s+"""',
    '"""`[DONE: <text>]` without chat.dialog should NOT bypass the gate."""',
    content
)
content = re.sub(
    r'# Outbound dispatched the body\n    assert sent_via_outbound, "DONE-with-body must dispatch as outbound reply"\n    assert "Example Domain" in sent_via_outbound\[0\]\n\n    # Audit event written\n    rows = substrate.connection.execute\(\n        "SELECT 1 FROM continuity_events "\n        "WHERE kind = \'internal.done_as_reply_dispatched\'"\n    \)\.fetchall\(\)\n    assert rows, "done_as_reply_dispatched audit event must fire"\n\n    # Session closed cleanly \(one LLM call, no gate blocks\)\n    assert provider\.calls == 1\n    gate_events = substrate\.connection\.execute\(\n        "SELECT COUNT\(\*\) FROM continuity_events "\n        "WHERE kind = \'internal.inbox_priority_gate\'"\n    \)\.fetchone\(\)\[0\]\n    assert gate_events == 0',
    '# Outbound did NOT dispatch\n    assert not sent_via_outbound\n    # Audit event written\n    gate_events = substrate.connection.execute(\n        "SELECT COUNT(*) FROM continuity_events "\n        "WHERE kind = \'internal.inbox_priority_gate\'"\n    ).fetchone()[0]\n    assert gate_events > 0',
    content
)

# 3. test_done_with_body_preserves_code_and_hides_reasoning
# Replace body with a skip or delete
content = re.sub(
    r'async def test_done_with_body_preserves_code_and_hides_reasoning.*?(?=\n\n\nasync def test_bare_done)',
    '',
    content,
    flags=re.DOTALL
)

with open(r"c:\Users\Jester\Desktop\Sonya\tests\sonya\test_agent_session_inbox_gate.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done rewriting tests!")
