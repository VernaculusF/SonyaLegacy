from __future__ import annotations

from sonya.memory.tool_experience import (
    ToolExperience,
    classify_outcome,
    extract_tool_tags,
)
from sonya.state.substrate import Substrate


def test_record_and_query_basic(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "texp.db")
    try:
        tx = ToolExperience(sub)
        entry = tx.record(
            tool_name="web.search",
            tool_arg_summary="python async patterns",
            outcome="success",
            outcome_detail="found 5 results",
            latency_ms=320,
            tags=("web", "succeeded"),
        )
        assert entry.tool_name == "web.search"
        assert entry.outcome == "success"
        assert entry.latency_ms == 320
        assert "web" in entry.tags

        rate = tx.success_rate(tool_name="web.search")
        assert rate["total"] == 1
        assert rate["success"] == 1
        assert rate["rate"] == 1.0
        assert rate["avg_latency_ms"] == 320
    finally:
        sub.close()


def test_record_errors_affect_success_rate(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "texp.db")
    try:
        tx = ToolExperience(sub)
        for _ in range(3):
            tx.record(tool_name="code.exec", outcome="success", latency_ms=100)
        for _ in range(2):
            tx.record(tool_name="code.exec", outcome="error", outcome_detail="[ERROR] timeout", latency_ms=5000)

        rate = tx.success_rate(tool_name="code.exec")
        assert rate["total"] == 5
        assert rate["success"] == 3
        assert rate["error"] == 2
        assert abs(rate["rate"] - 0.6) < 0.01
    finally:
        sub.close()


def test_classify_outcome() -> None:
    assert classify_outcome("[ERROR] something failed") == "error"
    assert classify_outcome("[BLOCKED] by policy") == "blocked"
    assert classify_outcome("[TIMEOUT] exceeded") == "timeout"
    assert classify_outcome("[MAX_STEPS] limit") == "partial"
    assert classify_outcome("[OK] done") == "success"
    assert classify_outcome("[SKIP] not available") == "partial"
    assert classify_outcome("some regular output") == "success"


def test_extract_tool_tags() -> None:
    tags = extract_tool_tags("subagent.spawn", '{"task":"check"}', "[OK] spawned")
    assert "subagent.spawn" in tags
    assert "tool_family:subagent" in tags
    assert "subagent" in tags
    assert "succeeded" in tags

    tags_err = extract_tool_tags("web.search", "test", "[ERROR] timeout")
    assert "failed" in tags_err
    assert "tool_family:web" in tags_err


def test_model_stats(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "texp.db")
    try:
        tx = ToolExperience(sub)
        tx.record(tool_name="subagent.spawn", outcome="success", provider="codexsale", model="gpt-5.4", latency_ms=1200)
        tx.record(tool_name="subagent.spawn", outcome="success", provider="codexsale", model="gpt-5.4", latency_ms=800)
        tx.record(tool_name="subagent.spawn", outcome="error", provider="codexsale", model="gpt-5.4-mini", latency_ms=5000)

        stats = tx.model_stats(provider="codexsale")
        assert len(stats) == 2
        gpt54 = next(s for s in stats if s["model"] == "gpt-5.4")
        assert gpt54["total"] == 2
        assert gpt54["success"] == 2
        assert gpt54["rate"] == 1.0

        gpt54mini = next(s for s in stats if s["model"] == "gpt-5.4-mini")
        assert gpt54mini["errors"] == 1
        assert gpt54mini["rate"] == 0.0
    finally:
        sub.close()


def test_episodic_mirror(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "texp.db")
    try:
        tx = ToolExperience(sub)
        tx.record(
            tool_name="subagent.spawn",
            outcome="success",
            provider="codexsale",
            model="gpt-5.4",
            tags=("subagent",),
        )

        from sonya.memory.episodic import EpisodicMemory
        ep = EpisodicMemory(sub)
        events = ep.get_by_type("tool_event", limit=5)
        assert len(events) == 1
        assert "subagent.spawn" in events[0].raw_content
        assert "success" in events[0].normalized_summary
    finally:
        sub.close()


def test_recent_errors(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "texp.db")
    try:
        tx = ToolExperience(sub)
        tx.record(tool_name="web.fetch", outcome="success")
        tx.record(tool_name="web.fetch", outcome="error", outcome_detail="timeout")
        tx.record(tool_name="web.fetch", outcome="error", outcome_detail="404")

        errors = tx.recent_errors(tool_name="web.fetch")
        assert len(errors) == 2
        assert all(e.outcome != "success" for e in errors)
    finally:
        sub.close()


def test_picker_uses_experience_bonus(tmp_path) -> None:
    from sonya.providers.keystore import KeyStore
    from sonya.tools.subagent_model_picker import pick_subagent_model

    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        store.add_key(provider="openrouter", name="or-1", api_key="or-key",
                       base_url="https://openrouter.ai/api/v1", model="")
        store.add_key(provider="codexsale", name="cx-1", api_key="cx-key",
                       base_url="https://codex.sale/v1", model="gpt-5.4-mini")

        tx = ToolExperience(sub)
        for _ in range(5):
            tx.record(tool_name="subagent.spawn", outcome="success",
                       provider="openrouter", model="poolside/laguna-m.1:free", latency_ms=200)
        for _ in range(5):
            tx.record(tool_name="subagent.spawn", outcome="error",
                       provider="codexsale", model="gpt-5.4-mini", latency_ms=8000)

        pick = pick_subagent_model("debug this code", store, substrate=sub)
        assert pick.provider == "openriver" or pick.provider == "openrouter"
    finally:
        sub.close()
