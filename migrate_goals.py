import re

with open('src/sonya/subject/agent_session.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_list = '''def _h_goals_list(arg: str, ctx: _ToolContext) -> str:
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] no substrate"
    from sonya.tasks.goals import GoalStore
    goals = GoalStore(sub).list_active()
    if not goals:
        return "(no active goals)"
    lines = ["Active goals:"]
    for g in goals:
        lines.append(f"  [{g.goal_id}] (prio={g.priority}) {g.title}")
        if g.description:
            lines.append(f"    {g.description[:150]}")
    return "\\n".join(lines)'''
new_list = '''def _h_goals_list(arg: str, ctx: _ToolContext) -> str:
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] no substrate"
    from sonya.work.store import WorkItemStore
    items = WorkItemStore(sub).list_open()
    goals = [i for i in items if i.item_type == "goal"]
    if not goals:
        return "(no active goals)"
    lines = ["Active goals:"]
    for g in goals:
        lines.append(f"  [{g.item_id}] {g.title}")
        if g.description:
            lines.append(f"    {g.description[:150]}")
    return "\\n".join(lines)'''
code = code.replace(old_list, new_list)

old_create = '''def _h_goals_create(arg: str, ctx: _ToolContext) -> str:
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] no substrate"
    from sonya.tasks.goals import GoalStore
    parts = arg.split("|")
    title = parts[0].strip() if parts else ""
    desc = parts[1].strip() if len(parts) > 1 else ""
    prio = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else 0
    if not title:
        return "[ERROR] goals.create needs: title | description | priority"
    g = GoalStore(sub).create(title, desc, prio)
    return f"[OK] goal created: {g.goal_id} — {g.title} (priority={g.priority})"'''
new_create = '''def _h_goals_create(arg: str, ctx: _ToolContext) -> str:
    if ctx.work is None:
        return "[ERROR] no work tool"
    parts = arg.split("|")
    title = parts[0].strip() if parts else ""
    desc = parts[1].strip() if len(parts) > 1 else ""
    if not title:
        return "[ERROR] goals.create needs: title | description"
    import json
    data = {"title": title, "description": desc, "item_type": "goal", "urgency": "background"}
    return ctx.work.create(json.dumps(data))'''
code = code.replace(old_create, new_create)

old_achieve = '''def _h_goals_achieve(arg: str, ctx: _ToolContext) -> str:
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] no substrate"
    from sonya.tasks.goals import GoalStore
    try:
        g = GoalStore(sub).achieve(arg.strip())
        return f"[OK] goal {g.goal_id} achieved: {g.title}"
    except KeyError:
        return f"[ERROR] goal {arg.strip()!r} not found"'''
new_achieve = '''def _h_goals_achieve(arg: str, ctx: _ToolContext) -> str:
    if ctx.work is None:
        return "[ERROR] no work tool"
    return ctx.work.complete(arg.strip())'''
code = code.replace(old_achieve, new_achieve)

old_abandon = '''def _h_goals_abandon(arg: str, ctx: _ToolContext) -> str:
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] no substrate"
    from sonya.tasks.goals import GoalStore
    try:
        g = GoalStore(sub).abandon(arg.strip())
        return f"[OK] goal {g.goal_id} abandoned: {g.title}"
    except KeyError:
        return f"[ERROR] goal {arg.strip()!r} not found"'''
new_abandon = '''def _h_goals_abandon(arg: str, ctx: _ToolContext) -> str:
    if ctx.work is None:
        return "[ERROR] no work tool"
    return ctx.work.fail(f"{arg.strip()}|abandoned")'''
code = code.replace(old_abandon, new_abandon)

with open('src/sonya/subject/agent_session.py', 'w', encoding='utf-8') as f:
    f.write(code)
