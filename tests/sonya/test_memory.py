from __future__ import annotations

from pathlib import Path

import pytest

from sonya.memory import ConsolidationPipeline, EpisodicMemory, MemoryCompiler, SemanticMemory
from sonya.project import ProjectRunStore, ProjectStore
from sonya.state import Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_episodic_record_and_retrieve(substrate: Substrate) -> None:
    mem = EpisodicMemory(substrate)
    event = mem.record(
        event_type="dialogue_event",
        raw_content="Привет, как дела?",
        normalized_summary="Ivan greeted Sonya",
        actor="ivan",
        channel="telegram",
        importance_score=0.6,
    )
    assert event.event_id.startswith("ep-")
    assert event.retention_strength == 1.0

    recent = mem.get_recent(limit=5)
    assert len(recent) == 1
    assert recent[0].raw_content == "Привет, как дела?"


def test_episodic_get_by_type(substrate: Substrate) -> None:
    mem = EpisodicMemory(substrate)
    mem.record(event_type="dialogue_event", raw_content="a")
    mem.record(event_type="tool_event", raw_content="b")
    mem.record(event_type="dialogue_event", raw_content="c")

    dialogues = mem.get_by_type("dialogue_event")
    assert len(dialogues) == 2


def test_episodic_mark_accessed_strengthens(substrate: Substrate) -> None:
    mem = EpisodicMemory(substrate)
    event = mem.record(event_type="dialogue_event", raw_content="y")
    mem.mark_accessed(event.event_id)

    recent = mem.get_recent()
    assert recent[0].access_count == 1
    # retention_strength stays at 1.0 (already max) but access_count proves retrieval happened
    assert recent[0].retention_strength == 1.0


def test_semantic_add_and_retrieve(substrate: Substrate) -> None:
    sem = SemanticMemory(substrate)
    fact = sem.add_fact(
        fact_type="relation_observation",
        statement="Когда Иван говорит тихо, он устал",
        confidence=0.8,
    )
    assert fact.fact_id.startswith("sf-")

    all_facts = sem.get_all()
    assert len(all_facts) == 1
    assert all_facts[0].statement == "Когда Иван говорит тихо, он устал"


def test_completed_project_outcome_enters_shared_memory_with_project_provenance(substrate: Substrate) -> None:
    project = ProjectStore(substrate).create("Shared outcome proof")
    ProjectStore(substrate).set_status(project.project_id, "completed", source="test")
    run_store = ProjectRunStore(substrate)
    run = run_store.create(project.project_id, kind="project_executor")
    run_store.start(run.run_id)
    run_store.complete(run.run_id, result="Delivered the dependency-aware project runtime")

    compiled = MemoryCompiler(substrate).run()

    facts = SemanticMemory(substrate).get_for_context(project_id=project.project_id, limit=10)
    project_facts = [fact for fact in facts if fact.project_id == project.project_id]
    assert compiled["project_summaries"] == 1
    assert len(project_facts) == 1
    assert project_facts[0].scope == "project"
    assert "Delivered the dependency-aware project runtime" in project_facts[0].statement


def test_project_outcome_memory_ignores_newer_subagent_runs(substrate: Substrate) -> None:
    project = ProjectStore(substrate).create("Project executor memory proof")
    run_store = ProjectRunStore(substrate)
    executor_run = run_store.create(project.project_id, kind="project_executor")
    run_store.start(executor_run.run_id)
    run_store.complete(executor_run.run_id, result="Executor result survives newer worker runs")
    for _ in range(4):
        worker_run = run_store.create(project.project_id, kind="subagent")
        run_store.start(worker_run.run_id)

    compiled = MemoryCompiler(substrate).run()

    facts = SemanticMemory(substrate).get_all(project_id=project.project_id, limit=10)
    assert compiled["project_summaries"] == 1
    assert any("Executor result survives newer worker runs" in fact.statement for fact in facts)


def test_semantic_reinforce(substrate: Substrate) -> None:
    sem = SemanticMemory(substrate)
    fact = sem.add_fact(fact_type="x", statement="y", confidence=0.5)
    sem.reinforce(fact.fact_id)

    all_facts = sem.get_all()
    assert all_facts[0].confidence == pytest.approx(0.6)


def test_consolidation_promotes_high_importance_to_candidates(substrate: Substrate) -> None:
    ep = EpisodicMemory(substrate)
    sem = SemanticMemory(substrate)
    pipeline = ConsolidationPipeline(ep, sem)

    ep.record(event_type="dialogue_event", raw_content="low", normalized_summary="low importance", importance_score=0.3)
    ep.record(event_type="dialogue_event", raw_content="high", normalized_summary="high importance observation", importance_score=0.9)

    created = pipeline.run_consolidation(min_importance=0.7)
    assert created == 1

    # Should be in candidates, not directly in semantic facts
    facts = sem.get_all()
    assert len(facts) == 0
    
    rows = substrate.connection.execute("SELECT statement FROM consolidation_candidates").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "high importance observation"

def test_compiler_evaluates_and_promotes_candidates(substrate: Substrate) -> None:
    compiler = MemoryCompiler(substrate)
    
    # Insert candidates manually to bypass _compile_semantic_facts filters
    substrate.connection.execute(
        "INSERT INTO consolidation_candidates(candidate_id, statement, eval_status, created_at) "
        "VALUES ('c1', 'short', 'pending', 'now')"
    )
    substrate.connection.execute(
        "INSERT INTO consolidation_candidates(candidate_id, statement, eval_status, created_at) "
        "VALUES ('c2', 'long enough statement to be approved', 'pending', 'now')"
    )
    substrate.connection.commit()
    
    promoted = compiler._evaluate_and_promote_candidates()
    assert promoted == 1
    
    facts = SemanticMemory(substrate).get_all()
    assert len(facts) == 1
    assert facts[0].statement == "long enough statement to be approved"
    
    # Check candidates table for statuses
    rows = substrate.connection.execute("SELECT statement, eval_status FROM consolidation_candidates").fetchall()
    status_map = {r[0]: r[1] for r in rows}
    assert status_map["short"] == "rejected"
    assert status_map["long enough statement to be approved"] == "approved"


def test_persistent_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    EpisodicMemory(sub1).record(event_type="dialogue_event", raw_content="persist")
    SemanticMemory(sub1).add_fact(fact_type="y", statement="persisted fact")
    sub1.close()

    sub2 = Substrate.open(db)
    try:
        events = EpisodicMemory(sub2).get_recent()
        assert len(events) == 1
        facts = SemanticMemory(sub2).get_all()
        assert len(facts) == 1
    finally:
        sub2.close()
