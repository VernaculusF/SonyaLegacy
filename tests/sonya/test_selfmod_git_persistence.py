"""Tests for SelfModTool._git_commit_and_push.

Why: deploy/update.sh on VPS does ``git reset --hard origin/develop``. Without
auto-commit + push from selfmod.apply, Sonya's selfmod changes would be wiped
on the next deploy. Approved selfmod (4 layers passed) goes directly to the
current branch (develop) — Sonya has self-modification authority, no
feature-branch detour needed. Tests use a tmp git repo to avoid touching the
real one.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sonya.selfmod.proposal import ProposalStatus, ProposalStore
from sonya.state.substrate import Substrate
from sonya.state import seed_identity_if_empty
from sonya.tools.selfmod_tool import SelfModTool


def _git(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t"}
    if env:
        full_env.update(env)
    import os
    for k in ("PATH", "HOME", "SystemRoot"):
        if k in os.environ:
            full_env[k] = os.environ[k]
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=full_env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True, timeout=5)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _git_available(), reason="git binary not on PATH")


@pytest.fixture
def repo_with_remote(tmp_path: Path) -> Path:
    """Build a project_root that's a real git repo with a 'remote' (bare repo)."""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _git(["init", "--bare"], cwd=bare)

    project = tmp_path / "project"
    project.mkdir()
    _git(["init", "-b", "develop"], cwd=project)
    _git(["remote", "add", "origin", str(bare)], cwd=project)

    # Seed an initial commit so we have a HEAD to branch off
    (project / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "README.md"], cwd=project)
    _git(["commit", "-m", "seed"], cwd=project)
    _git(["push", "-u", "origin", "develop"], cwd=project)

    # Create the writable subdirs SELFMOD_WRITABLE_SUBPATHS expects
    (project / "src" / "sonya" / "tools").mkdir(parents=True)
    return project


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    db = tmp_path / "test.db"
    sub = Substrate.open(db)
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


@pytest.fixture
def selfmod(substrate: Substrate, repo_with_remote: Path) -> SelfModTool:
    return SelfModTool(substrate, project_root=repo_with_remote)


def _propose_and_force_approve(
    sm: SelfModTool, substrate: Substrate, *, target: str, summary: str, content: str
) -> str:
    """Force-approve to test git step in isolation from validation layers."""
    create = json.loads(sm.propose(
        target_module=target,
        change_summary=summary,
        new_content=content,
    ))
    pid = create["proposal_id"]
    ProposalStore(substrate).update_status(pid, ProposalStatus.APPROVED)
    return pid


def test_apply_pushes_to_current_branch(
    selfmod: SelfModTool, substrate: Substrate, repo_with_remote: Path
) -> None:
    """End-to-end: force-approved proposal + apply should push to current branch.

    Sonya's selfmod has full validation authority (4 layers); approved
    changes go straight to develop, no feature-branch detour.
    """
    pid = _propose_and_force_approve(
        selfmod, substrate,
        target="src/sonya/tools/git_test_tool.py",
        summary="add a tool that exists for git test",
        content="VALUE = 42\n",
    )

    result = json.loads(selfmod.apply(pid))
    assert result["status"] == "applied"

    git_info = result.get("git", {})
    assert git_info.get("ok") is True, f"git push failed: {git_info}"
    # Should be on whatever branch was checked out (develop in fixture)
    assert git_info["branch"] == "develop"
    assert git_info["commit_sha"]

    # Verify the bare remote actually received the commit on develop
    remote = repo_with_remote.parent / "remote.git"
    log = subprocess.run(
        ["git", "log", "-1", "--format=%H", "develop"],
        cwd=str(remote),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert log == git_info["commit_sha"]

    # Working tree should still be on develop (no feature-branch detour)
    current = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(repo_with_remote),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert current == "develop"


def test_apply_silent_when_not_a_git_repo(
    substrate: Substrate, tmp_path: Path
) -> None:
    """If project_root isn't a git repo, apply still succeeds; git result has error."""
    project = tmp_path / "no_git"
    (project / "src" / "sonya" / "tools").mkdir(parents=True)
    sm = SelfModTool(substrate, project_root=project)

    pid = _propose_and_force_approve(
        sm, substrate,
        target="src/sonya/tools/no_git_tool.py",
        summary="no git here",
        content="X = 1\n",
    )

    result = json.loads(sm.apply(pid))
    assert result["status"] == "applied"
    git_info = result.get("git", {})
    assert git_info.get("ok") is False
    assert "not a git repo" in git_info.get("error", "")


def test_git_commit_includes_proposal_id_and_summary(
    selfmod: SelfModTool, substrate: Substrate, repo_with_remote: Path
) -> None:
    """Commit message should embed proposal_id and target so blame attribution is clean."""
    pid = _propose_and_force_approve(
        selfmod, substrate,
        target="src/sonya/tools/commit_msg_tool.py",
        summary="readable commit message",
        content="A = 1\n",
    )

    result = json.loads(selfmod.apply(pid))
    git_info = result.get("git", {})
    assert git_info.get("ok") is True, f"git push failed: {git_info}"

    # Read the commit message from develop on the remote
    remote = repo_with_remote.parent / "remote.git"
    log = subprocess.run(
        ["git", "log", "-1", "--format=%B", "develop"],
        cwd=str(remote),
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert pid in log
    assert "readable commit message" in log
    assert "src/sonya/tools/commit_msg_tool.py" in log
    # Author should be Sonya, not the test runner's git config
    author = subprocess.run(
        ["git", "log", "-1", "--format=%an <%ae>", "develop"],
        cwd=str(remote),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert "Sonya" in author


def test_apply_refuses_detached_head(
    substrate: Substrate, repo_with_remote: Path
) -> None:
    """If working tree is in detached HEAD, refuse to commit (would lose work)."""
    # Detach HEAD
    subprocess.run(
        ["git", "checkout", "--detach", "HEAD"],
        cwd=str(repo_with_remote),
        check=True,
        capture_output=True,
    )

    sm = SelfModTool(substrate, project_root=repo_with_remote)
    pid = _propose_and_force_approve(
        sm, substrate,
        target="src/sonya/tools/detached_tool.py",
        summary="should refuse",
        content="DETACHED = True\n",
    )

    result = json.loads(sm.apply(pid))
    # File still gets written + hot-reloaded — apply is best-effort
    assert result["status"] == "applied"
    git_info = result.get("git", {})
    assert git_info.get("ok") is False
    assert "detached" in git_info.get("error", "").lower()
