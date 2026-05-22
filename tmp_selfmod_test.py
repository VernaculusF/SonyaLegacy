"""End-to-end selfmod pipeline test on VPS.

Создаёт тривиальный proposal: добавить docstring в src/sonya/skills/__init__.py.
Прогоняет propose → test_sandbox → validate → apply → проверяет файл.

Если что-то фейлится — печатает где и почему.
"""
import json
import sys
import os
from pathlib import Path

# Ensure imports work when run from /tmp
sys.path.insert(0, "/home/jester-sonya/Sonya/src")
sys.path.insert(0, "/home/jester-sonya/Sonya/packages/tg-userbot/src")

from sonya.state.substrate import Substrate
from sonya.tools.selfmod_tool import SelfModTool

NEW_CONTENT = '''"""Skills system: registry, trust levels, executor, builtins.

Каждый skill — это поведенческая единица с trust level, activation rules
и опционально исполнимым кодом. Builtins регистрируются автоматически
на startup через SkillsTool.register_builtins().
"""
from __future__ import annotations

from sonya.skills.registry import SkillAlreadyExistsError, SkillNotFoundError, SkillRegistry
from sonya.skills.skill import Skill
from sonya.skills.trust import TrustLevel

__all__ = [
    "Skill",
    "SkillAlreadyExistsError",
    "SkillNotFoundError",
    "SkillRegistry",
    "TrustLevel",
]
'''

TARGET = "src/sonya/skills/__init__.py"
SUMMARY = "Add module docstring to skills/__init__.py — first end-to-end selfmod cycle test"

def main():
    sub_path = Path("/home/jester-sonya/.sonya/sonya_substrate.db")
    print(f"=== Opening substrate at {sub_path} ===")
    sub = Substrate.open(sub_path, read_only=False)
    project_root = Path("/home/jester-sonya/Sonya")
    tool = SelfModTool(sub, project_root=project_root)

    print("\n=== STEP 1: propose ===")
    res = json.loads(tool.propose(
        target_module=TARGET,
        change_summary=SUMMARY,
        new_content=NEW_CONTENT,
        proposed_by="ivan",  # Иван трекает что это его тестовый proposal
    ))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if res.get("status") not in ("created",):
        print("ABORT: propose failed")
        sub.close()
        return 1
    pid = res["proposal_id"]

    print(f"\n=== STEP 2: test_sandbox {pid} ===")
    res = json.loads(tool.test_sandbox(pid))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res.get("ok", res.get("status") in ("sandbox_ok", "ok")):
        # sandbox_test returns status=ok | sandbox_failed; check actual key
        if res.get("status") == "sandbox_failed":
            print("ABORT: sandbox test failed")
            sub.close()
            return 2
        # If shape is different, just continue and see what validate says

    print(f"\n=== STEP 3: validate {pid} (Layers 1-4) ===")
    res = json.loads(tool.validate(pid))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    final_status = res.get("final_status")
    if final_status not in ("approved", "governed_approved"):
        print(f"ABORT: validate did not reach approved status, got '{final_status}'")
        sub.close()
        return 3

    print(f"\n=== STEP 4: apply {pid} ===")
    # Capture file content before apply
    file_path = project_root / TARGET
    before = file_path.read_text(encoding="utf-8") if file_path.exists() else "(not exists)"
    print(f"Before apply ({len(before)} chars):")
    print(before[:300])

    res = json.loads(tool.apply(pid))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if res.get("status") != "applied":
        print("ABORT: apply failed")
        sub.close()
        return 4

    print(f"\n=== STEP 5: verify file changed ===")
    after = file_path.read_text(encoding="utf-8")
    print(f"After apply ({len(after)} chars):")
    print(after[:500])
    if after == before:
        print("ABORT: file content unchanged")
        sub.close()
        return 5
    if "Skills system: registry, trust levels" not in after:
        print("ABORT: expected docstring not found in file")
        sub.close()
        return 6

    print(f"\n=== STEP 6: check proposal status in substrate ===")
    final_p = tool._store.get(pid)
    print(f"Final status: {final_p.status.value}")

    sub.close()
    print("\n=== SUCCESS — full selfmod pipeline works end-to-end ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
