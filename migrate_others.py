import os

def migrate_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()

    # Imports
    code = code.replace('from sonya.tasks.models import TaskStatus, TaskUrgency', 'from sonya.work.models import WorkItemStatus, WorkItemUrgency')
    code = code.replace('from sonya.tasks.service import TaskService', 'from sonya.work.service import WorkItemService')
    code = code.replace('from sonya.tasks.store import TaskStore', 'from sonya.work.store import WorkItemStore')
    code = code.replace('from sonya.tasks.goals import GoalStore', 'from sonya.work.store import WorkItemStore')
    code = code.replace('from sonya.tasks.models import TaskStatus as _TS', 'from sonya.work.models import WorkItemStatus as _TS')
    code = code.replace('from sonya.tasks.models import TaskStatus', 'from sonya.work.models import WorkItemStatus')
    code = code.replace('from sonya.tasks.models import TaskNotFoundError', 'from sonya.work.models import WorkItemNotFoundError')

    # Classes
    code = code.replace('TaskStore', 'WorkItemStore')
    code = code.replace('TaskService', 'WorkItemService')
    code = code.replace('TaskStatus', 'WorkItemStatus')
    code = code.replace('TaskUrgency', 'WorkItemUrgency')
    code = code.replace('GoalStore', 'WorkItemStore')
    code = code.replace('TaskNotFoundError', 'WorkItemNotFoundError')
    code = code.replace('task_id', 'item_id')

    # Specific replacements
    code = code.replace('t.task_id', 't.item_id')
    code = code.replace('t.created_by', 't.origin')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)

files_to_migrate = [
    'src/sonya/main.py',
    'src/sonya/admin/server.py',
    'src/sonya/planning/context_builder.py'
]

for f in files_to_migrate:
    migrate_file(f)
