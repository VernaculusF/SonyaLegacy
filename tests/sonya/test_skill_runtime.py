"""Runtime skill registry + executor tests (substrate v22)."""
from __future__ import annotations

import pytest

from sonya.skills.executor import SkillExecutor, runtime_skills_dir
from sonya.skills.registry import SkillRegistry
from sonya.skills.skill import Skill
from sonya.skills.trust import TrustLevel
from sonya.state.substrate import Substrate
from sonya.tools.skills_tool import SkillsTool


@pytest.fixture
def substrate(tmp_path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_module_path_persists(substrate):
    reg = SkillRegistry(substrate)
    reg.register(
        Skill(
            skill_id="skill-x",
            name="X",
            purpose="X",
            module_path="sonya.skills.builtins.memory_search",
        )
    )
    loaded = reg.get("skill-x")
    assert loaded.module_path == "sonya.skills.builtins.memory_search"


def test_executor_uses_module_path_from_registry(substrate):
    """When the registry row carries module_path, the executor honours it
    rather than the legacy hardcoded mapping."""
    reg = SkillRegistry(substrate)
    reg.register(
        Skill(
            skill_id="skill-mem-alias",
            name="alias",
            purpose="alias-of-memory-search",
            trust_level=TrustLevel.CORE_TRUSTED,
            module_path="sonya.skills.builtins.memory_search",
        )
    )
    out = SkillExecutor(reg, substrate).execute("skill-mem-alias", {"query": "test"})
    # Returning anything that isn't [ERROR] means the import succeeded.
    assert not out.startswith("[ERROR]"), out


def test_register_runtime_writes_file_and_runs(substrate, monkeypatch, tmp_path):
    # Redirect runtime skills dir to tmp so we don't pollute the user's home.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    tool = SkillsTool(substrate)
    block = (
        "skill-greet|greet|say hi|experimental\n"
        "def run(ctx):\n"
        "    return 'hi ' + ctx.get('query', '')\n"
    )
    res = tool.register_runtime(block)
    assert res.startswith("[OK]"), res
    written = (
        tmp_path / ".sonya" / "runtime_skills" / "skill-greet.py"
    )
    assert written.exists()

    # Now actually run it via the executor.
    out = tool.run("skill-greet world")
    assert out.strip() == "hi world", out


def test_register_runtime_overwrites_in_place(substrate, monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    tool = SkillsTool(substrate)
    block_v1 = (
        "skill-bump|bump|first version|experimental\n"
        "def run(ctx): return 'v1'\n"
    )
    assert tool.register_runtime(block_v1).startswith("[OK]")
    assert tool.run("skill-bump").strip() == "v1"

    block_v2 = (
        "skill-bump|bump|second version|experimental\n"
        "def run(ctx): return 'v2'\n"
    )
    res2 = tool.register_runtime(block_v2)
    assert "[OK]" in res2
    # Module is loaded fresh on each execute via SourceFileLoader, so v2
    # is visible immediately without process restart.
    assert tool.run("skill-bump").strip() == "v2"


def test_register_runtime_rejects_bad_id(substrate, monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    tool = SkillsTool(substrate)
    bad = (
        "Bad ID!|x|x|experimental\n"
        "def run(ctx): return 'x'\n"
    )
    res = tool.register_runtime(bad)
    assert res.startswith("[ERROR]") and "skill_id" in res


def test_register_runtime_rejects_syntax_error(substrate, monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    tool = SkillsTool(substrate)
    bad = (
        "skill-broken|x|x|experimental\n"
        "def run(ctx return 1\n"  # syntax error
    )
    res = tool.register_runtime(bad)
    assert res.startswith("[ERROR]") and "syntax" in res


def test_register_runtime_requires_run_function(substrate, monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    tool = SkillsTool(substrate)
    bad = (
        "skill-no-run|x|x|experimental\n"
        "def helper(ctx): return 'nope'\n"
    )
    res = tool.register_runtime(bad)
    assert res.startswith("[ERROR]") and "run" in res


def test_register_builtins_backfills_module_path_on_legacy_row(substrate):
    """If a row was registered before v22 (no module_path), calling
    register_builtins again should backfill it."""
    reg = SkillRegistry(substrate)
    # Simulate legacy row — same id as the builtin but no module_path.
    reg.register(
        Skill(
            skill_id="skill-memory-search",
            name="memory-search",
            purpose="legacy",
            trust_level=TrustLevel.CORE_TRUSTED,
            module_path="",
        )
    )
    tool = SkillsTool(substrate)
    out = tool.register_builtins()
    assert "[OK]" in out
    refreshed = reg.get("skill-memory-search")
    assert refreshed.module_path == "sonya.skills.builtins.memory_search"


def test_runtime_skills_dir_is_created():
    p = runtime_skills_dir()
    assert p.exists() and p.is_dir()
