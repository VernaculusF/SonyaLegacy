"""Manual trigger: ask the running InternalProcess to fire an active session ASAP.

Appends an `internal.active_session_requested_external` event to the substrate.
The running loop polls for new events of that kind every tick (~30s) and pulls
its schedule back so `should_active` becomes True on the next tick.

Usage on VPS:
    /home/jester-sonya/Sonya/.venv/bin/python \\
        /home/jester-sonya/Sonya/deploy/trigger_active_session.py [reason]

Reason is free text (default: "manual_cli"). Multiple invocations queue
multiple sessions — each new event re-arms the trigger.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running without setting PYTHONPATH
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sonya.config import load_config
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.substrate import Substrate


def main() -> int:
    reason = sys.argv[1] if len(sys.argv) > 1 else "manual_cli"
    config = load_config()
    sub = Substrate.open(config.substrate_path, read_only=False)
    try:
        stream = ContinuityStream(sub)
        ev = ContinuityEvent(
            kind="internal.active_session_requested_external",
            payload={"reason": reason, "source": "deploy/trigger_active_session.py"},
        )
        seq = stream.append(ev)
        print(f"appended seq={seq.seq} kind={ev.kind} reason={reason}")
        print("InternalProcess will pick this up on its next tick (within ~30s).")
    finally:
        sub.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
