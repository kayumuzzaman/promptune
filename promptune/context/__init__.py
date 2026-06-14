"""Context fingerprinting: gather environment signals."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import (
    TimeoutError as FuturesTimeout,
)
from dataclasses import dataclass
from typing import Any, Callable

from promptune.context.collectors import (
    EnvironmentContext,
    GitContext,
    ShellHistoryContext,
    TechStackContext,
    collect_environment,
    collect_git,
    collect_shell_history,
    collect_tech_stack,
)


@dataclass
class ContextFingerprint:
    """Aggregated context from all collectors."""

    git: GitContext
    shell: ShellHistoryContext
    tech: TechStackContext
    env: EnvironmentContext


def _default_git() -> GitContext:
    return GitContext(
        branch="",
        recent_commits=[],
        modified_files=[],
        diff_stats="",
        stash_count=0,
    )


def _default_shell() -> ShellHistoryContext:
    return ShellHistoryContext(
        recent_commands=[],
        error_patterns=[],
        session_intent="unknown",
    )


def _default_tech() -> TechStackContext:
    return TechStackContext(
        languages=[],
        frameworks=[],
        package_manager=None,
    )


def _default_env() -> EnvironmentContext:
    return EnvironmentContext(
        in_venv=False,
        in_container=False,
        in_ci=False,
        in_ssh=False,
    )


def collect_context(
    timeout_ms: int = 400,
) -> ContextFingerprint:
    """Run all collectors in parallel with timeout."""
    timeout_s = timeout_ms / 1000.0

    collectors: dict[
        str,
        tuple[Callable[[], Any], Callable[[], Any]],
    ] = {
        "git": (collect_git, _default_git),
        "shell": (collect_shell_history, _default_shell),
        "tech": (collect_tech_stack, _default_tech),
        "env": (collect_environment, _default_env),
    }

    results: dict = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures: dict[str, Future[Any]] = {
            name: executor.submit(fn)
            for name, (fn, _) in collectors.items()
        }

        for name, future in futures.items():
            _, default_fn = collectors[name]
            try:
                results[name] = future.result(
                    timeout=timeout_s
                )
            except (FuturesTimeout, Exception):
                results[name] = default_fn()

    return ContextFingerprint(
        git=results["git"],
        shell=results["shell"],
        tech=results["tech"],
        env=results["env"],
    )
