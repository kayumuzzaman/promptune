"""Task 6: Context Fingerprinting — context ranker tests."""

from __future__ import annotations

from promptune.context import ContextFingerprint
from promptune.context.collectors import (
    EnvironmentContext,
    GitContext,
    ShellHistoryContext,
    TechStackContext,
)
from promptune.context.ranker import rank_context


def test_rank_includes_branch() -> None:
    """Git branch is highest priority — always included."""
    fp = ContextFingerprint(
        git=GitContext(
            branch="fix/auth-redirect",
            recent_commits=["abc|2h|fix auth"],
            modified_files=["src/auth.py"],
            diff_stats="1 file changed",
            stash_count=0,
        ),
        shell=ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        ),
        tech=TechStackContext(
            languages=["python"],
            frameworks=["flask"],
            package_manager="pip",
        ),
        env=EnvironmentContext(
            in_venv=True,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )

    result = rank_context(fp, token_budget=50)

    assert "fix/auth-redirect" in result


def test_rank_respects_token_budget() -> None:
    """Output fits within token budget."""
    fp = ContextFingerprint(
        git=GitContext(
            branch="main",
            recent_commits=[
                f"hash{i}|{i}h|commit {i}"
                for i in range(20)
            ],
            modified_files=[
                f"file{i}.py" for i in range(50)
            ],
            diff_stats="50 files changed",
            stash_count=3,
        ),
        shell=ShellHistoryContext(
            recent_commands=["pytest", "git status"] * 20,
            error_patterns=["FAILED"],
            session_intent="debugging",
        ),
        tech=TechStackContext(
            languages=["python", "typescript"],
            frameworks=["flask", "react", "nextjs"],
            package_manager="pnpm",
        ),
        env=EnvironmentContext(
            in_venv=True,
            in_container=True,
            in_ci=False,
            in_ssh=True,
        ),
    )

    result = rank_context(fp, token_budget=100)

    word_count = len(result.split())
    assert word_count <= 120


def test_rank_drops_low_priority_first() -> None:
    """With tiny budget, only highest priority signals."""
    fp = ContextFingerprint(
        git=GitContext(
            branch="main",
            recent_commits=["abc|2h|fix auth"],
            modified_files=["src/auth.py"],
            diff_stats="1 file changed",
            stash_count=2,
        ),
        shell=ShellHistoryContext(
            recent_commands=["pytest"],
            error_patterns=[],
            session_intent="unknown",
        ),
        tech=TechStackContext(
            languages=["python"],
            frameworks=["flask"],
            package_manager="pip",
        ),
        env=EnvironmentContext(
            in_venv=True,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )

    result = rank_context(fp, token_budget=5)

    # Branch (priority 1) should survive
    assert "main" in result
    # Stash (priority 10) should be dropped
    assert "stash" not in result


def test_rank_empty_context() -> None:
    """Empty fingerprint returns empty string."""
    fp = ContextFingerprint(
        git=GitContext(
            branch="",
            recent_commits=[],
            modified_files=[],
            diff_stats="",
            stash_count=0,
        ),
        shell=ShellHistoryContext(
            recent_commands=[],
            error_patterns=[],
            session_intent="unknown",
        ),
        tech=TechStackContext(
            languages=[],
            frameworks=[],
            package_manager=None,
        ),
        env=EnvironmentContext(
            in_venv=False,
            in_container=False,
            in_ci=False,
            in_ssh=False,
        ),
    )

    result = rank_context(fp, token_budget=500)

    assert result == ""
