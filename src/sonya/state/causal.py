import contextvars
from contextlib import contextmanager
from typing import Iterator

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")
causal_parent_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("causal_parent_id", default="")

@contextmanager
def causal_context(correlation_id: str, causal_parent_id: str = "") -> Iterator[None]:
    """Set the causal context for the current async task / thread.
    
    All ContinuityEvents emitted within this context will automatically
    receive these IDs in their payload, allowing reconstruction of the
    causal graph (e.g. request -> planner -> executor -> message).
    """
    c_token = correlation_id_var.set(correlation_id)
    p_token = causal_parent_id_var.set(causal_parent_id)
    try:
        yield
    finally:
        correlation_id_var.reset(c_token)
        causal_parent_id_var.reset(p_token)
