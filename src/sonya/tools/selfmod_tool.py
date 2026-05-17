"""Self-modification tool surface for Sonya.

Exposes the 4-layer self-modification pipeline as agent-callable tools.
This is the primary mechanism by which Sonya extends her own system
**without process restart**.

Flow:
  1. `selfmod.propose target | summary | new_content` — записывает в substrate
  2. `selfmod.test_sandbox proposal_id` — изолированный import-test (опционально, рекомендовано)
  3. `selfmod.validate proposal_id` — Layers 1-4
  4. Если REQUIRES_GOVERNED_CHANGE → `selfmod.governed proposal_id` → ждать approve
  5. Если APPROVED/GOVERNED_APPROVED → `selfmod.apply proposal_id`
     - сохраняет pre-state (текущее содержимое файла) в proposal
     - пишет файл на диск
     - вызывает hot-reload через LiveRuntime
     - запускает 60-секундный watch window
     - при crash в этом окне → auto-rollback из pre-state

  6. `selfmod.rollback proposal_id [reason]` — ручной откат (восстанавливает pre-state)

См.: docs/SYSTEM_BUILDOUT_PLAN.md Этап A, SUBSTRATE_STANCE §9.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from sonya.harness.approval import ApprovalManager
from sonya.harness.audit import AuditLog
from sonya.runtime.live import get_live_runtime
from sonya.selfmod import (
    GovernedChangeProtocol,
    Pipeline,
    ProposalStatus,
    ProposalStore,
    SelfModificationProposal,
    WatchWindow,
)
from sonya.selfmod.proposal import ProposalNotFoundError
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.substrate import Substrate
from sonya.tools.module_loader import (
    discover_subclasses,
    path_to_dotted,
    reload_module,
    sandbox_test,
)


# Subpaths inside src/sonya/ that selfmod is allowed to modify.
SELFMOD_WRITABLE_SUBPATHS: tuple[str, ...] = (
    "src/sonya/channels",
    "src/sonya/tools",
    "src/sonya/skills",
    "src/sonya/planning",
    "src/sonya/initiative",
    "src/sonya/memory",
    "src/sonya/anchor",
    "src/sonya/embodiment",
    "src/sonya/simulation",
    "src/sonya/admin",
    "src/sonya/tasks",
    "src/sonya/subject",
    "src/sonya/runtime",
    "src/sonya/providers",
    "src/sonya/harness",
    "src/sonya/main.py",
    "src/sonya/config.py",
    "src/sonya/logging.py",
    "tests/sonya",
)

# Hard forbidden — even via selfmod pipeline.
SELFMOD_FORBIDDEN_SUBPATHS: tuple[str, ...] = (
    "src/sonya/state/seed.py",
    "src/sonya/state/schema.sql",
    "src/sonya/state/identity.py",
    "src/sonya/selfmod/layers/anchor_integrity.py",
    ".env",
    ".git",
    "tg.session",
    "docs/personality/SOUL.md",
    "docs/core",
)


# Marker prefixes used inside diff_blob to distinguish content types
_NEW_CONTENT_MARKER = "FULL_CONTENT:\n"
_PRE_STATE_MARKER = "\n\n---PRE_STATE_BEFORE_APPLY---\n"


class SelfModTool:
    """Agent-callable wrapper for the self-modification pipeline."""

    def __init__(
        self,
        substrate: Substrate,
        project_root: Path | None = None,
        *,
        primary_anchor_principal_id: str = "ivan",
    ) -> None:
        self._sub = substrate
        self._root = (
            project_root or Path(__file__).resolve().parent.parent.parent.parent
        ).resolve()
        self._store = ProposalStore(substrate)
        self._stream = ContinuityStream(substrate)
        self._audit = AuditLog(substrate)
        self._approvals = ApprovalManager(substrate)
        self._pipeline = Pipeline(self._store, self._stream, self._audit)
        self._governed = GovernedChangeProtocol(
            self._store,
            self._approvals,
            primary_anchor_principal_id=primary_anchor_principal_id,
        )
        self._watchdog = WatchWindow(self._store, self._stream)

    # --- safety helpers ---

    def _check_target_writable(self, target_module: str) -> str | None:
        target = target_module.replace("\\", "/").lstrip("/")
        for forbidden in SELFMOD_FORBIDDEN_SUBPATHS:
            if target == forbidden or target.startswith(forbidden + "/"):
                return f"target_module '{target}' is in SELFMOD_FORBIDDEN_SUBPATHS"
        for allowed in SELFMOD_WRITABLE_SUBPATHS:
            if target == allowed or target.startswith(allowed + "/"):
                return None
        return (
            f"target_module '{target}' not in SELFMOD_WRITABLE_SUBPATHS. "
            f"Use plugins/ or workspace/ for unstructured changes."
        )

    def _extract_new_content(self, diff_blob: str) -> str | None:
        """Extract the new file content from a proposal's diff_blob."""
        if not diff_blob.startswith(_NEW_CONTENT_MARKER):
            return None
        body = diff_blob[len(_NEW_CONTENT_MARKER):]
        # Strip pre-state if it was already appended (after first apply)
        if _PRE_STATE_MARKER in body:
            body = body.split(_PRE_STATE_MARKER, 1)[0]
        return body

    def _extract_pre_state(self, diff_blob: str) -> str | None:
        """Extract pre-state content captured at apply time."""
        if _PRE_STATE_MARKER not in diff_blob:
            return None
        return diff_blob.split(_PRE_STATE_MARKER, 1)[1]

    # --- public tool methods ---

    def propose(
        self,
        target_module: str,
        change_summary: str,
        new_content: str = "",
        diff_blob: str = "",
        proposed_by: str | None = None,
    ) -> str:
        err = self._check_target_writable(target_module)
        if err:
            return json.dumps({"status": "rejected_pre_pipeline", "reason": err})
        if not new_content and not diff_blob:
            return json.dumps({
                "status": "error",
                "reason": "either new_content or diff_blob required",
            })
        blob = diff_blob or f"{_NEW_CONTENT_MARKER}{new_content}"
        proposal = self._store.create(
            target_module=target_module,
            change_summary=change_summary,
            diff_blob=blob,
            proposed_by_principal_id=proposed_by or "sonya",
        )
        return json.dumps({
            "status": "created",
            "proposal_id": proposal.proposal_id,
            "target_module": proposal.target_module,
            "current_status": proposal.status.value,
        })

    def test_sandbox(self, proposal_id: str) -> str:
        """Import the proposed content in an isolated namespace.

        Catches syntax errors, import errors, top-level exceptions BEFORE writing to disk.
        Does NOT modify any live module.
        """
        try:
            p = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})

        content = self._extract_new_content(p.diff_blob)
        if content is None:
            return json.dumps({"status": "error", "reason": "diff_blob missing FULL_CONTENT marker"})

        result = sandbox_test(p.target_module, content)
        self._stream.append(ContinuityEvent(
            kind="self_mod.sandbox_test",
            payload={
                "proposal_id": proposal_id,
                "target_module": p.target_module,
                "ok": result["ok"],
                "error": result["error"][:200] if result.get("error") else "",
            },
        ))
        return json.dumps({
            "status": "tested",
            "proposal_id": proposal_id,
            "ok": result["ok"],
            "error": result["error"],
            "traceback": result["traceback"][:2000],
            "exports": result["exports"],
        })

    def validate(self, proposal_id: str) -> str:
        try:
            proposal = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})
        results = self._pipeline.validate(proposal)
        final = self._store.get(proposal_id)
        return json.dumps({
            "status": "validated",
            "proposal_id": proposal_id,
            "final_status": final.status.value,
            "layers": [
                {"layer": r.layer, "passed": r.passed, "reason": r.reason}
                for r in results
            ],
        })

    def apply(self, proposal_id: str) -> str:
        """Apply approved proposal: capture pre-state, write file, hot-reload.

        Returns JSON with hot_reload result and watch_window scheduling info.
        Process restart is NOT required for most subpaths — see the
        `hot_reload` field in the result.
        """
        try:
            proposal = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})

        if proposal.status not in (ProposalStatus.APPROVED, ProposalStatus.GOVERNED_APPROVED):
            return json.dumps({
                "status": "error",
                "reason": f"proposal status is {proposal.status.value}, must be approved or governed_approved",
            })

        err = self._check_target_writable(proposal.target_module)
        if err:
            return json.dumps({"status": "error", "reason": err})

        new_content = self._extract_new_content(proposal.diff_blob)
        if new_content is None:
            return json.dumps({
                "status": "error",
                "reason": "only FULL_CONTENT proposals are applicable. Use new_content parameter.",
            })

        target_path = (self._root / proposal.target_module).resolve()
        try:
            target_path.relative_to(self._root)
        except ValueError:
            return json.dumps({"status": "error", "reason": "target outside project root"})

        # Capture pre-state (None if file didn't exist)
        pre_state: str | None = None
        if target_path.exists():
            try:
                pre_state = target_path.read_text(encoding="utf-8")
            except Exception:
                pre_state = None

        # Persist pre-state into the proposal so rollback can use it
        new_blob = proposal.diff_blob
        if pre_state is not None and _PRE_STATE_MARKER not in new_blob:
            new_blob = new_blob + _PRE_STATE_MARKER + pre_state
            self._sub.connection.execute(
                "UPDATE self_mod_proposals SET diff_blob = ? WHERE proposal_id = ?",
                (new_blob, proposal_id),
            )
            self._sub.connection.commit()

        # Write to disk
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(new_content, encoding="utf-8")

        # Mark applied
        self._store.update_status(proposal_id, ProposalStatus.APPLIED)
        self._stream.append(ContinuityEvent(
            kind="self_mod.applied",
            payload={
                "proposal_id": proposal_id,
                "target_module": proposal.target_module,
                "summary": proposal.change_summary,
                "size": len(new_content),
                "had_pre_state": pre_state is not None,
            },
        ))
        self._audit.append(
            principal_id=proposal.proposed_by_principal_id,
            action="selfmod.apply",
            decision="applied",
            scope=f"selfmod.{proposal.target_module}",
            metadata={"proposal_id": proposal_id},
        )

        # Hot-reload + drop-and-recreate
        reload_result = self._hot_reload(proposal.target_module)

        # Schedule watch window (rollback on crash within window)
        self._schedule_watch_window(proposal_id, proposal.target_module, watch_seconds=60)

        return json.dumps({
            "status": "applied",
            "proposal_id": proposal_id,
            "target_module": proposal.target_module,
            "bytes_written": len(new_content),
            "pre_state_captured": pre_state is not None,
            "hot_reload": reload_result,
            "watch_window_seconds": 60,
            "note": "if hot_reload.success=true, change is live; otherwise restart still needed",
        })

    def rollback(self, proposal_id: str, reason: str = "") -> str:
        """Restore pre-state captured at apply time."""
        try:
            proposal = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})

        if proposal.status != ProposalStatus.APPLIED:
            return json.dumps({
                "status": "error",
                "reason": f"can only rollback APPLIED proposals (current: {proposal.status.value})",
            })

        pre_state = self._extract_pre_state(proposal.diff_blob)
        target_path = (self._root / proposal.target_module).resolve()
        try:
            target_path.relative_to(self._root)
        except ValueError:
            return json.dumps({"status": "error", "reason": "target outside project root"})

        # Restore file
        if pre_state is None:
            # File didn't exist before — delete it
            if target_path.exists():
                target_path.unlink()
            file_action = "deleted (was new file)"
        else:
            target_path.write_text(pre_state, encoding="utf-8")
            file_action = f"restored ({len(pre_state)} bytes)"

        self._watchdog.trigger_revert(proposal, reason=reason or "manual rollback")

        # Hot-reload again to pick up restored content
        reload_result = self._hot_reload(proposal.target_module)

        return json.dumps({
            "status": "reverted",
            "proposal_id": proposal_id,
            "file_action": file_action,
            "hot_reload": reload_result,
            "reason": reason,
        })

    def list_proposals(self, status_filter: str = "") -> str:
        if status_filter:
            try:
                status = ProposalStatus(status_filter.strip().lower())
            except ValueError:
                return json.dumps({
                    "status": "error",
                    "reason": f"unknown status: {status_filter}",
                })
            proposals = self._store.list_by_status(status)
        else:
            proposals = []
            for s in ProposalStatus:
                proposals.extend(self._store.list_by_status(s))
            proposals.sort(key=lambda p: p.created_at, reverse=True)
            proposals = proposals[:50]
        return json.dumps({
            "status": "ok",
            "count": len(proposals),
            "proposals": [
                {
                    "proposal_id": p.proposal_id,
                    "target_module": p.target_module,
                    "summary": p.change_summary[:100],
                    "status": p.status.value,
                    "created_at": p.created_at,
                }
                for p in proposals
            ],
        })

    def get_proposal(self, proposal_id: str) -> str:
        try:
            p = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})
        # Strip pre-state from displayed diff_blob (it bloats output)
        display_blob = p.diff_blob
        if _PRE_STATE_MARKER in display_blob:
            display_blob = display_blob.split(_PRE_STATE_MARKER, 1)[0]
        return json.dumps({
            "status": "ok",
            "proposal_id": p.proposal_id,
            "target_module": p.target_module,
            "change_summary": p.change_summary,
            "diff_blob": display_blob[:5000],
            "diff_blob_truncated": len(display_blob) > 5000,
            "has_pre_state": _PRE_STATE_MARKER in p.diff_blob,
            "proposed_by": p.proposed_by_principal_id,
            "current_status": p.status.value,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })

    def request_governed(self, proposal_id: str) -> str:
        try:
            p = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})
        if p.status != ProposalStatus.REQUIRES_GOVERNED_CHANGE:
            return json.dumps({
                "status": "error",
                "reason": f"proposal status is {p.status.value}, expected requires_governed_change",
            })
        req = self._governed.request_governed_change(p)
        return json.dumps({
            "status": "approval_requested",
            "proposal_id": proposal_id,
            "approval_request_id": req.request_id,
            "note": "waiting for primary anchor approval via admin panel",
        })

    def check_governed(self, proposal_id: str) -> str:
        try:
            p = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})
        approved = self._governed.check_governed_approval(p)
        p_after = self._store.get(proposal_id)
        return json.dumps({
            "status": "checked",
            "proposal_id": proposal_id,
            "approved": approved,
            "current_status": p_after.status.value,
        })

    # --- hot-reload internals ---

    def _hot_reload(self, target_module: str) -> dict[str, Any]:
        """Reload the changed module + drop-and-recreate live instances.

        Returns dict with: success, dotted_name, channels_replaced, errors.
        """
        result: dict[str, Any] = {
            "success": False,
            "dotted_name": "",
            "channels_replaced": [],
            "tools_replaced": [],
            "soft_restart_required": False,
            "errors": [],
        }

        target = target_module.replace("\\", "/").lstrip("/")

        # Files that need full-process restart (cannot hot-reload)
        # main.py + config.py drive the event loop itself
        # logging.py / runtime/live.py affect process-wide state
        restart_only = {
            "src/sonya/main.py",
            "src/sonya/config.py",
            "src/sonya/logging.py",
            "src/sonya/runtime/live.py",
        }
        if target in restart_only:
            result["soft_restart_required"] = True
            result["errors"].append(
                f"{target} requires soft-restart of runtime task; "
                "use selfmod.soft_restart_runtime when supervisor pattern is enabled"
            )
            return result

        # Skip non-Python files (schema.sql, .md, etc.)
        if not target.endswith(".py"):
            result["success"] = True  # nothing to reload
            return result

        dotted = path_to_dotted(target)
        result["dotted_name"] = dotted

        # Reload the module
        try:
            module = reload_module(dotted)
        except Exception as err:
            result["errors"].append(f"reload failed: {type(err).__name__}: {err}")
            self._stream.append(ContinuityEvent(
                kind="self_mod.hot_reload_failed",
                payload={"dotted": dotted, "error": str(err)},
            ))
            return result

        # Reconcile live subsystems
        live = get_live_runtime()
        if live is None:
            # No live runtime registered (e.g. tests) — module reload succeeded, that's it
            result["success"] = True
            return result

        # Channel reconciliation
        if target.startswith("src/sonya/channels/") and target != "src/sonya/channels/__init__.py":
            try:
                self._reconcile_channels(module, live, result)
            except Exception as err:
                result["errors"].append(f"channel reconcile failed: {type(err).__name__}: {err}")

        # Tool reconciliation: for tools/, reloading the module is enough
        # because agent_session creates fresh instances each session.
        if target.startswith("src/sonya/tools/") and not target.endswith("/__init__.py"):
            result["tools_replaced"].append(dotted)

        result["success"] = not result["errors"]
        self._stream.append(ContinuityEvent(
            kind="self_mod.hot_reloaded",
            payload={
                "target": target,
                "dotted": dotted,
                "success": result["success"],
                "channels_replaced": result["channels_replaced"],
                "errors": result["errors"][:3],
            },
        ))
        return result

    def _reconcile_channels(self, module: Any, live: Any, result: dict[str, Any]) -> None:
        """Discover Channel implementations in module, drop-and-recreate.

        For each Channel subclass found:
          - if same name already in registry → stop old, instantiate new from class, start
          - if new name → instantiate with default args (channel may need config; if so it needs a factory)
        """
        from sonya.channels import Channel, ChannelRegistry

        registry: ChannelRegistry | None = live.channel_registry
        deps = live.channel_deps
        if registry is None or deps is None:
            return

        channel_classes = discover_subclasses(module, Channel)
        if not channel_classes:
            return

        loop = asyncio.get_event_loop()

        for cls in channel_classes:
            # Channels need __init__ args; we can only auto-replace channels
            # that already exist (we know their config).
            # New channels need an explicit registration call from agent code.
            existing_name = getattr(cls, "name", None)
            if existing_name and registry.get(existing_name) is not None:
                # Stop and recreate
                old = registry.get(existing_name)
                try:
                    if loop.is_running():
                        # We're inside the loop — schedule
                        asyncio.create_task(self._replace_channel(registry, deps, existing_name, cls, result))
                        result["channels_replaced"].append(f"{existing_name} (scheduled)")
                    else:
                        loop.run_until_complete(self._replace_channel(registry, deps, existing_name, cls, result))
                        result["channels_replaced"].append(existing_name)
                except Exception as err:
                    result["errors"].append(f"replace {existing_name}: {err}")

    async def _replace_channel(self, registry: Any, deps: Any, name: str, new_cls: type, result: dict[str, Any]) -> None:
        """Stop old channel instance, instantiate new class with same constructor args, start."""
        try:
            old = registry.get(name)
            if old is None:
                return
            # Capture old's __init__ args from its slots/dict
            init_args = {}
            for attr in ("_api_id", "_api_hash", "_session_path"):
                if hasattr(old, attr):
                    # Strip leading underscore for kwarg name
                    init_args[attr.lstrip("_")] = getattr(old, attr)

            await old.stop()
            registry.unregister(name)

            new_instance = new_cls(**init_args)
            registry.register(new_instance)
            await registry.start_one(name)
        except Exception as err:
            result["errors"].append(f"replace {name} failed: {type(err).__name__}: {err}")
            self._stream.append(ContinuityEvent(
                kind="self_mod.channel_replace_failed",
                payload={"name": name, "error": str(err)},
            ))

    def _schedule_watch_window(self, proposal_id: str, target_module: str, watch_seconds: int = 60) -> None:
        """Watch for crash signals over `watch_seconds`; auto-rollback if detected.

        For now the only signal is: subsequent `internal.tool_error` or
        `tg_handler_crash` event in continuity within the window AND
        mentioning the same dotted path.

        Real rollback logic runs only when an event loop is available.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._watch_loop(proposal_id, target_module, watch_seconds))
        except RuntimeError:
            # No event loop — running in tests or sync context. Skip.
            pass

    async def _watch_loop(self, proposal_id: str, target_module: str, watch_seconds: int) -> None:
        """Background task: poll continuity for crash signals; auto-rollback if found."""
        start_seq = self._stream.latest_seq()
        deadline = time.time() + watch_seconds
        dotted = path_to_dotted(target_module)
        crash_kinds = {"internal.tool_error", "tg_handler_crash", "self_mod.hot_reload_failed", "self_mod.channel_replace_failed"}

        while time.time() < deadline:
            await asyncio.sleep(5.0)
            try:
                events = list(self._stream.read_since(start_seq))
                for e in events:
                    if e.kind in crash_kinds:
                        # Heuristic: crash event mentions our dotted name OR target_module
                        payload_str = json.dumps(e.payload, ensure_ascii=False)
                        if dotted in payload_str or target_module in payload_str or e.kind == "self_mod.hot_reload_failed":
                            self._stream.append(ContinuityEvent(
                                kind="self_mod.auto_rollback_triggered",
                                payload={
                                    "proposal_id": proposal_id,
                                    "trigger_kind": e.kind,
                                    "trigger_seq": e.seq,
                                },
                            ))
                            self.rollback(proposal_id, reason=f"auto-rollback: {e.kind}")
                            return
            except Exception:
                pass
