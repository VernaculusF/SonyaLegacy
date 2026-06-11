"""Project API routes — hosted web runtime for Atrium.

Projects are long-lived activity contexts with consent-based policy.
Each project is a separate chat window with its own history, runs,
execution traces, and policy governing what Sonya can do autonomously.
"""

from __future__ import annotations

import json
from typing import Any

from sonya.config import load_config
from sonya.state import Substrate

try:
    from aiohttp import web
except ImportError:
    raise ImportError("Install aiohttp: pip install aiohttp")


def _get_substrate(config) -> Substrate:
    return Substrate.open(config.substrate_path)


def _get_substrate_writable(config) -> Substrate:
    return Substrate.open(config.substrate_path, read_only=False)


def _cors(response: web.Response) -> web.Response:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


def _project_run_payload(run: Any) -> dict[str, Any]:
    steps = [step for step in run.steps if isinstance(step, dict)]
    completed = sum(1 for step in steps if step.get("status") == "done")
    failed = sum(1 for step in steps if step.get("status") == "failed")
    cancelled = sum(1 for step in steps if step.get("status") == "cancelled")
    running = max(0, len(steps) - completed - failed - cancelled)
    terminal = completed + failed + cancelled
    percent = round((terminal / len(steps)) * 100) if steps else (
        100 if run.status in ("completed", "failed", "cancelled") else 0
    )
    return {
        "run_id": run.run_id,
        "kind": run.kind,
        "status": run.status,
        "agent_type": run.agent_type,
        "summary": run.summary,
        "steps": steps,
        "progress": {
            "total": len(steps),
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "running": running,
            "percent": percent,
        },
        "result": run.result[:2000] if run.result else "",
        "error": run.error[:2000] if run.error else "",
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "created_at": run.created_at,
    }


async def api_project_list(request: web.Request) -> web.Response:
    config = request.app["config"]
    status_filter = request.query.get("status", "")
    sub = _get_substrate(config)
    try:
        from sonya.project import ProjectStore
        store = ProjectStore(sub)
        projects = store.list_all(status=status_filter) if status_filter else store.list_all()
        return _cors(web.json_response({
            "count": len(projects),
            "projects": [
                {
                    "project_id": p.project_id,
                    "title": p.title,
                    "description": p.description,
                    "workspace_path": p.workspace_path,
                    "status": p.status,
                    "owner_principal_id": p.owner_principal_id,
                    "policy": p.policy,
                    "last_activity_at": p.last_activity_at,
                    "created_at": p.created_at,
                }
                for p in projects
            ],
        }))
    finally:
        sub.close()


async def api_project_get(request: web.Request) -> web.Response:
    config = request.app["config"]
    project_id = request.match_info["project_id"]
    sub = _get_substrate(config)
    try:
        from sonya.project import ProjectStore
        from sonya.project.model import ProjectNotFoundError
        store = ProjectStore(sub)
        try:
            p = store.get(project_id)
        except ProjectNotFoundError:
            return _cors(web.json_response({"error": "not found"}, status=404))
        return _cors(web.json_response({
            "project_id": p.project_id,
            "title": p.title,
            "description": p.description,
            "workspace_path": p.workspace_path,
            "status": p.status,
            "owner_principal_id": p.owner_principal_id,
            "policy": p.policy,
            "last_activity_at": p.last_activity_at,
            "created_at": p.created_at,
        }))
    finally:
        sub.close()


async def api_project_create(request: web.Request) -> web.Response:
    config = request.app["config"]
    try:
        data = await request.json()
    except Exception:
        data = {}
    title = str(data.get("title") or "").strip()
    if not title:
        return _cors(web.json_response({"error": "title required"}, status=400))
    description = str(data.get("description") or "")
    workspace_path = str(data.get("workspace_path") or "")
    owner = str(data.get("owner_principal_id") or "ivan")
    policy = data.get("policy") or None
    sub = _get_substrate_writable(config)
    try:
        from sonya.project import ProjectStore
        store = ProjectStore(sub)
        p = store.create(title, description=description,
                         workspace_path=workspace_path,
                         owner_principal_id=owner,
                         policy=policy)
        return _cors(web.json_response({
            "project_id": p.project_id,
            "title": p.title,
            "status": p.status,
        }, status=201))
    finally:
        sub.close()


async def api_project_update(request: web.Request) -> web.Response:
    config = request.app["config"]
    project_id = request.match_info["project_id"]
    try:
        data = await request.json()
    except Exception:
        data = {}
    sub = _get_substrate_writable(config)
    try:
        from sonya.project import ProjectStore
        from sonya.project.model import ProjectNotFoundError
        store = ProjectStore(sub)
        try:
            store.get(project_id)
        except ProjectNotFoundError:
            return _cors(web.json_response({"error": "not found"}, status=404))
        kwargs = {}
        for k in ("title", "description", "workspace_path", "policy"):
            if k in data:
                kwargs[k] = data[k]
        p = store.update(project_id, **kwargs) if kwargs else store.get(project_id)
        if "status" in data:
            try:
                p = store.set_status(
                    project_id,
                    str(data["status"]),
                    reason=str(data.get("reason") or ""),
                    source="project_api",
                )
            except ValueError as exc:
                return _cors(web.json_response({"error": str(exc)}, status=400))
        return _cors(web.json_response({
            "project_id": p.project_id,
            "title": p.title,
            "status": p.status,
        }))
    finally:
        sub.close()


async def api_project_delete(request: web.Request) -> web.Response:
    config = request.app["config"]
    project_id = request.match_info["project_id"]
    sub = _get_substrate_writable(config)
    try:
        from sonya.project import ProjectStore
        from sonya.project.model import ProjectNotFoundError
        store = ProjectStore(sub)
        try:
            store.get(project_id)
        except ProjectNotFoundError:
            return _cors(web.json_response({"error": "not found"}, status=404))
        store.delete(project_id)
        return _cors(web.json_response({"status": "deleted", "project_id": project_id}))
    finally:
        sub.close()


async def api_project_runs(request: web.Request) -> web.Response:
    config = request.app["config"]
    project_id = request.match_info["project_id"]
    kind = request.query.get("kind", "")
    sub = _get_substrate(config)
    try:
        from sonya.project import ProjectRunStore
        store = ProjectRunStore(sub)
        runs = store.list_by_project(project_id, kind=kind)
        return _cors(web.json_response({
            "project_id": project_id,
            "runs": [_project_run_payload(run) for run in runs],
        }))
    finally:
        sub.close()


async def api_project_traces(request: web.Request) -> web.Response:
    config = request.app["config"]
    project_id = request.match_info["project_id"]
    step_type = request.query.get("step_type", "")
    sub = _get_substrate(config)
    try:
        from sonya.project import ExecutionTraceStore
        store = ExecutionTraceStore(sub)
        traces = store.list_by_project(project_id, step_type=step_type, limit=100)
        return _cors(web.json_response({
            "project_id": project_id,
            "traces": [
                {
                    "trace_id": t.trace_id,
                    "run_id": t.run_id,
                    "step_seq": t.step_seq,
                    "step_type": t.step_type,
                    "content": t.content[:1000],
                    "tool_name": t.tool_name,
                    "outcome": t.outcome,
                    "model": t.model,
                    "provider": t.provider,
                    "created_at": t.created_at,
                }
                for t in traces
            ],
        }))
    finally:
        sub.close()


async def api_project_run_cancel(request: web.Request) -> web.Response:
    config = request.app["config"]
    project_id = request.match_info["project_id"]
    run_id = request.match_info["run_id"]
    sub = _get_substrate_writable(config)
    try:
        from sonya.project import ExecutionTraceStore, ProjectRunStore
        from sonya.project.model import RunNotFoundError
        from sonya.subject.subagent_lifecycle import cancel_subagent

        run_store = ProjectRunStore(sub)
        try:
            run = run_store.get(run_id)
        except RunNotFoundError:
            return _cors(web.json_response({"error": "run not found"}, status=404))
        if run.project_id != project_id:
            return _cors(web.json_response({"error": "run not found"}, status=404))
        cancelled = 0
        for step in run.steps:
            if not isinstance(step, dict) or step.get("status") in ("done", "failed", "cancelled"):
                continue
            if cancel_subagent(sub, str(step.get("subagent_id", "")), reason="project run cancelled"):
                cancelled += 1
            step["status"] = "cancelled"
            step["result"] = "[CANCELLED] project run cancelled"
        run_store.update(run_id, status="cancelled", steps=run.steps, error="[CANCELLED] project run cancelled")
        traces = ExecutionTraceStore(sub).list_by_run(run_id)
        ExecutionTraceStore(sub).append(
            run_id,
            project_id,
            step_seq=(max(trace.step_seq for trace in traces) + 1) if traces else 0,
            step_type="checkpoint",
            content=f"project run cancelled; workers={cancelled}",
            outcome="cancelled",
        )
        return _cors(web.json_response({
            "status": "cancelled",
            "run_id": run_id,
            "cancelled_workers": cancelled,
        }))
    finally:
        sub.close()


async def api_project_run_control(request: web.Request) -> web.Response:
    config = request.app["config"]
    project_id = request.match_info["project_id"]
    run_id = request.match_info["run_id"]
    action = request.match_info["action"]
    if action not in ("pause", "resume", "approve", "deny"):
        return _cors(web.json_response({"error": "invalid action"}, status=400))
    sub = _get_substrate_writable(config)
    try:
        from sonya.project import ExecutionTraceStore, ProjectRunStore
        from sonya.project.model import RunNotFoundError

        store = ProjectRunStore(sub)
        try:
            run = store.get(run_id)
        except RunNotFoundError:
            return _cors(web.json_response({"error": "run not found"}, status=404))
        if run.project_id != project_id:
            return _cors(web.json_response({"error": "run not found"}, status=404))
        if action == "pause" and run.status not in ("pending", "running"):
            return _cors(web.json_response({"error": f"cannot pause {run.status} run"}, status=409))
        if action == "resume" and run.status != "paused":
            return _cors(web.json_response({"error": f"cannot resume {run.status} run"}, status=409))
        if action in ("approve", "deny") and run.status != "waiting_approval":
            return _cors(web.json_response({"error": f"cannot decide {run.status} run"}, status=409))
        if action in ("approve", "deny"):
            approval = next(
                (step for step in reversed(run.steps) if isinstance(step, dict) and step.get("kind") == "approval" and not step.get("decision")),
                None,
            )
            if approval is None:
                return _cors(web.json_response({"error": "pending approval not found"}, status=409))
            approval["decision"] = action
            approval["status"] = "done"
            status = "running" if action == "approve" else "paused"
            store.update(run_id, status=status, steps=run.steps)
        else:
            status = "paused" if action == "pause" else "running"
            store.update(run_id, status=status)
        traces = ExecutionTraceStore(sub).list_by_run(run_id)
        ExecutionTraceStore(sub).append(
            run_id,
            project_id,
            step_seq=(max(trace.step_seq for trace in traces) + 1) if traces else 0,
            step_type="checkpoint",
            content=(
                "project orchestration paused; running provider requests may finish"
                if action == "pause" else (
                    "project orchestration resumed" if action == "resume"
                    else f"project approval decision: {action}"
                )
            ),
            outcome=status,
        )
        return _cors(web.json_response({"status": status, "run_id": run_id}))
    finally:
        sub.close()


async def api_project_check_policy(request: web.Request) -> web.Response:
    config = request.app["config"]
    project_id = request.match_info["project_id"]
    try:
        data = await request.json()
    except Exception:
        data = {}
    action = str(data.get("action") or "").strip()
    if not action:
        return _cors(web.json_response({"error": "action required"}, status=400))
    sub = _get_substrate(config)
    try:
        from sonya.project import ProjectStore
        from sonya.project.model import ProjectNotFoundError
        store = ProjectStore(sub)
        try:
            p = store.get(project_id)
        except ProjectNotFoundError:
            return _cors(web.json_response({"error": "not found"}, status=404))
        if p.policy_forbids(action):
            verdict = "forbidden"
        elif p.policy_requires_consent(action):
            verdict = "consent"
        else:
            verdict = "allowed"
        return _cors(web.json_response({
            "project_id": project_id,
            "action": action,
            "verdict": verdict,
        }))
    finally:
        sub.close()


async def api_evolution_pressure(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        rows = sub.connection.execute(
            "SELECT pressure_id, dimension, current_score, target_score, "
            "gap, evidence, last_evaluated_at FROM evolution_pressure "
            "ORDER BY gap DESC"
        ).fetchall()
        return _cors(web.json_response({
            "dimensions": [
                {
                    "dimension": r[1],
                    "current_score": r[2],
                    "target_score": r[3],
                    "gap": r[4],
                    "evidence": r[5],
                    "last_evaluated_at": r[6],
                }
                for r in rows
            ],
        }))
    finally:
        sub.close()


async def api_workspace_policy_get(request: web.Request) -> web.Response:
    config = request.app["config"]
    workspace_id = request.match_info.get("workspace_id", "main")
    sub = _get_substrate(config)
    try:
        from sonya.project import WorkspacePolicyStore
        store = WorkspacePolicyStore(sub)
        wp = store.get(workspace_id)
        return _cors(web.json_response({
            "workspace_id": wp.workspace_id,
            "policy": wp.policy,
            "full_system_access": wp.full_system_access,
            "allowed_paths": wp.allowed_paths,
            "denied_paths": wp.denied_paths,
        }))
    finally:
        sub.close()


async def api_workspace_policy_set(request: web.Request) -> web.Response:
    config = request.app["config"]
    workspace_id = request.match_info.get("workspace_id", "main")
    try:
        data = await request.json()
    except Exception:
        data = {}
    sub = _get_substrate_writable(config)
    try:
        from sonya.project import WorkspacePolicyStore
        from sonya.project.model import WorkspacePolicy
        store = WorkspacePolicyStore(sub)
        wp = store.get(workspace_id)
        if "full_system_access" in data:
            store.set_full_system_access(workspace_id, bool(data["full_system_access"]))
        elif "policy" in data:
            wp.policy = data["policy"]
            store.set(wp)
        wp = store.get(workspace_id)
        return _cors(web.json_response({
            "workspace_id": wp.workspace_id,
            "full_system_access": wp.full_system_access,
            "policy": wp.policy,
        }))
    finally:
        sub.close()


def register_project_routes(app: web.Application) -> None:
    app.router.add_get("/api/projects", api_project_list)
    app.router.add_get("/api/projects/{project_id}", api_project_get)
    app.router.add_post("/api/projects", api_project_create)
    app.router.add_post("/api/projects/{project_id}", api_project_update)
    app.router.add_delete("/api/projects/{project_id}", api_project_delete)
    app.router.add_get("/api/projects/{project_id}/runs", api_project_runs)
    app.router.add_post("/api/projects/{project_id}/runs/{run_id}/cancel", api_project_run_cancel)
    app.router.add_post("/api/projects/{project_id}/runs/{run_id}/{action}", api_project_run_control)
    app.router.add_get("/api/projects/{project_id}/traces", api_project_traces)
    app.router.add_post("/api/projects/{project_id}/check-policy", api_project_check_policy)
    app.router.add_get("/api/evolution-pressure", api_evolution_pressure)
    app.router.add_get("/api/workspace-policy", api_workspace_policy_get)
    app.router.add_get("/api/workspace-policy/{workspace_id}", api_workspace_policy_get)
    app.router.add_post("/api/workspace-policy/{workspace_id}", api_workspace_policy_set)
