import re

with open('src/sonya/subject/internal_loop.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Imports
code = code.replace('from sonya.tasks.models import TaskStatus, TaskUrgency', 'from sonya.work.models import WorkItemStatus, WorkItemUrgency')
code = code.replace('from sonya.tasks.service import TaskService', 'from sonya.work.service import WorkItemService')
code = code.replace('from sonya.tasks.store import TaskStore', 'from sonya.work.store import WorkItemStore')
code = code.replace('from sonya.tools.tasks_tool import TasksTool', 'from sonya.tools.work_tool import WorkTool')

# 2. Classes
code = code.replace('TaskStore', 'WorkItemStore')
code = code.replace('TaskService', 'WorkItemService')
code = code.replace('TasksTool', 'WorkTool')
code = code.replace('TaskStatus', 'WorkItemStatus')
code = code.replace('TaskUrgency', 'WorkItemUrgency')

# 3. Method calls and variables
code = code.replace('tasks_tool =', 'work_tool =')
code = code.replace('"tasks": tasks_tool,', '"work": work_tool,')
code = code.replace('default_created_by="self"', 'default_origin="self"')

# 4. Handle remaining_steps properly before renaming variables
code = re.sub(r'(\w+)\.remaining_steps\(\)', '[]', code)

# 5. Rename variable names task -> item
code = re.sub(r'\btask_id\b', 'item_id', code)
code = re.sub(r'\bnext_task\b', 'next_item', code)
code = re.sub(r'\btask\b( \=|\.|\:)', r'item\1', code)
code = code.replace('for task in', 'for item in')

# 6. Fix properties on the item model
code = code.replace('item.task_id', 'item.item_id')
code = code.replace('item.created_by', 'item.origin')
code = code.replace('item.is_ivan_task()', '(item.origin == "ivan")')
code = code.replace('item.notify_mode', '"progress"')

# 7. Continuity events rename
code = code.replace('task.session_handoff', 'work.session_handoff')

with open('src/sonya/subject/internal_loop.py', 'w', encoding='utf-8') as f:
    f.write(code)
