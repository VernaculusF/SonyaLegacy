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
    event = mem.record(event_type="x", raw_content="y")
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


def test_semantic_reinforce(substrate: Substrate) -> None:
    sem = SemanticMemory(substrate)
    fact = sem.add_fact(fact_type="x", statement="y", confidence=0.5)
    sem.reinforce(fact.fact_id)

    all_facts = sem.get_all()
    assert all_facts[0].confidence == pytest.approx(0.6)


def test_consolidation_promotes_high_importance(substrate: Substrate) -> None:
    ep = EpisodicMemory(substrate)
    sem = SemanticMemory(substrate)
    pipeline = ConsolidationPipeline(ep, sem)

    ep.record(event_type="x", raw_content="low", normalized_summary="low importance", importance_score=0.3)
    ep.record(event_type="x", raw_content="high", normalized_summary="high importance observation", importance_score=0.9)

    created = pipeline.run_consolidation(min_importance=0.7)
    assert created == 1

    facts = sem.get_all()
    assert len(facts) == 1
    assert facts[0].statement == "high importance observation"


def test_persistent_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    EpisodicMemory(sub1).record(event_type="x", raw_content="persist")
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
