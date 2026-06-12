import re

with open('src/sonya/subject/agent_session.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Imports
code = code.replace('from sonya.tools.tasks_tool import TasksTool', 'from sonya.tools.work_tool import WorkTool')
code = code.replace('TasksTool | None', 'WorkTool | None')

# 2. ToolContext and usages
code = code.replace('self.tasks = tasks', 'self.work = work')
code = code.replace('ctx.tasks', 'ctx.work')
code = code.replace('tasks=tasks,', 'work=work,')

# 3. Tool registry strings
code = code.replace('"tasks.', '"work.')
code = code.replace('tasks.*', 'work.*')
code = re.sub(r'\btasks\.(create|list|get|pick|complete|fail|block|unblock|pause|handoff|plan|step)\b', r'work.\1', code)

# 4. Handler names and logic
code = code.replace('_h_tasks_', '_h_work_')
code = code.replace('_require(ctx.work, "tasks")', '_require(ctx.work, "work")')

# 5. Fix custom logic in complete/fail handlers
code = code.replace('def _notify_ivan_on_task_end(task_id: str, notify_text: str, ctx: _ToolContext, prefix: str = "") -> None:', 'def _notify_ivan_on_task_end(item_id: str, notify_text: str, ctx: _ToolContext, prefix: str = "") -> None:')
code = code.replace('task = ctx.work._service.get(task_id)', 'item = ctx.work._service.get(item_id)')

# Replace the broken notify_mode logic
old_notify = '''    # Look up notify_mode
    try:
        task = ctx.work._service.get(task_id)
    except Exception:
        return ""
    if task.notify_mode == "silent":
        return ""'''
new_notify = '''    try:
        item = ctx.work._service.get(task_id)
    except Exception:
        return ""'''
code = code.replace(old_notify, new_notify)

# Replace the title usage in notification
old_title = '''title=f"Task {task_id}",'''
new_title = '''title=f"WorkItem {item_id}",'''
code = code.replace(old_title, new_title)

old_def_notify = '''def _notify_ivan_on_task_end(
    *,
    ctx: _ToolContext,
    task_id: str,
    notify_text: str,
    title: str,
) -> str:'''
new_def_notify = '''def _notify_ivan_on_task_end(
    *,
    ctx: _ToolContext,
    item_id: str,
    notify_text: str,
    title: str,
) -> str:'''
code = code.replace(old_def_notify, new_def_notify)

# Update tasks in tool documentation list
old_doc = '''- tasks.create — block form, JSON: {'''
new_doc = '''- work.create — block form, JSON: {'''
code = code.replace(old_doc, new_doc)

with open('src/sonya/subject/agent_session.py', 'w', encoding='utf-8') as f:
    f.write(code)
