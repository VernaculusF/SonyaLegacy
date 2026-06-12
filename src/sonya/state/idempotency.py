import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sonya.state.substrate import Substrate


def acquire_idempotency(substrate: "Substrate", key: str) -> bool:
    """Attempt to acquire a durable idempotency key.

    Returns True if the key was newly acquired, False if it already exists.
    Used by background processes (like maintenance ticks or event handlers)
    to ensure a side-effect is applied exactly once across restarts.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        substrate.connection.execute(
            "INSERT INTO idempotency_keys (key, created_at) VALUES (?, ?)",
            (key, now),
        )
        substrate.connection.commit()
        return True
    except sqlite3.IntegrityError:
        return False
