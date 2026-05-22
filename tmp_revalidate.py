"""Re-validate smod-2c022e15 with the new (fixed) Layer 4 logic."""
import sys
sys.path.insert(0, "/home/jester-sonya/Sonya/src")
sys.path.insert(0, "/home/jester-sonya/Sonya/packages/tg-userbot/src")

from pathlib import Path
from sonya.state.substrate import Substrate
from sonya.tools.selfmod_tool import SelfModTool
from sonya.selfmod import ProposalStore
from sonya.selfmod.proposal import ProposalStatus
import json

PID = "smod-2c022e15376f4641ae28f1370dc4c1eb"

sub = Substrate.open(Path("/home/jester-sonya/.sonya/sonya_substrate.db"), read_only=False)
store = ProposalStore(sub)
p = store.get(PID)
print(f"Current status: {p.status.value}")

# Reset status to draft so pipeline can re-validate
store.update_status(PID, ProposalStatus.DRAFT)
print("Reset to draft")

# Run validate
tool = SelfModTool(sub, project_root=Path("/home/jester-sonya/Sonya"))
res = json.loads(tool.validate(PID))
print(json.dumps(res, indent=2, ensure_ascii=False))

# If approved — apply
if res.get("final_status") == "approved":
    print("\n=== Applying ===")
    apply_res = json.loads(tool.apply(PID))
    print(json.dumps(apply_res, indent=2, ensure_ascii=False))

sub.close()
