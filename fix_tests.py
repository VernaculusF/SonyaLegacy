import sys
with open('tests/sonya/test_memory.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace event_type="x" with event_type="dialogue_event" so it's not a trace
content = content.replace('event_type="x"', 'event_type="dialogue_event"')
with open('tests/sonya/test_memory.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)

with open('tests/sonya/test_tool_experience.py', 'r', encoding='utf-8') as f:
    content = f.read()

# ToolExperience now writes to TraceLayer, not EpisodicMemory
target = '''        from sonya.memory.episodic import EpisodicMemory
        ep = EpisodicMemory(sub)
        events = ep.get_by_type("tool_event", limit=5)
        assert len(events) == 1'''
replacement = '''        from sonya.memory.trace_layer import TraceLayer
        from sonya.memory.types import RecordType
        trace = TraceLayer(sub)
        events = trace.get_by_type(RecordType.subagent_trace, limit=5)
        assert len(events) == 1'''
content = content.replace(target, replacement)
with open('tests/sonya/test_tool_experience.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("Done fix_tests")
