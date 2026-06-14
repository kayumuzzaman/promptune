"""Context ranker — prioritizes signals within token budget."""

from __future__ import annotations

from promptune.context import ContextFingerprint
from promptune.context.sanitizer import sanitize


def rank_context(
    fp: ContextFingerprint, token_budget: int = 500
) -> str:
    """Rank context signals by priority and fit budget."""
    signals: list[tuple[int, str, str]] = []

    if fp.git.branch:
        signals.append((1, "branch", fp.git.branch))
    if fp.git.recent_commits:
        commits = "; ".join(fp.git.recent_commits[:5])
        signals.append((2, "recent_commits", commits))
    if fp.git.modified_files:
        files = ", ".join(fp.git.modified_files[:10])
        signals.append((3, "modified_files", files))
    if fp.git.diff_stats:
        signals.append((4, "diff_stats", fp.git.diff_stats))
    if fp.tech.languages:
        signals.append(
            (5, "stack", ",".join(fp.tech.languages))
        )
    if fp.shell.recent_commands:
        cmds = "; ".join(fp.shell.recent_commands[-5:])
        signals.append((6, "recent_cmds", cmds))
    if fp.shell.error_patterns:
        errs = "; ".join(fp.shell.error_patterns[:3])
        signals.append((7, "errors", errs))
    if fp.tech.frameworks:
        signals.append(
            (8, "frameworks", ",".join(fp.tech.frameworks))
        )
    if fp.tech.package_manager:
        signals.append(
            (8, "pkg", fp.tech.package_manager)
        )

    env_flags: list[str] = []
    if fp.env.in_venv:
        env_flags.append("venv")
    if fp.env.in_container:
        env_flags.append("container")
    if fp.env.in_ci:
        env_flags.append("ci")
    if fp.env.in_ssh:
        env_flags.append("ssh")
    if env_flags:
        signals.append(
            (9, "env", ",".join(env_flags))
        )

    if fp.shell.session_intent != "unknown":
        signals.append(
            (9, "intent", fp.shell.session_intent)
        )

    if fp.git.stash_count > 0:
        signals.append(
            (10, "stash", str(fp.git.stash_count))
        )

    if not signals:
        return ""

    signals.sort(key=lambda s: s[0])

    parts: list[str] = []
    word_count = 0

    for _, key, value in signals:
        entry = f"{key}={value}"
        entry_words = len(entry.split())
        if word_count + entry_words > token_budget:
            break
        parts.append(entry)
        word_count += entry_words

    result = " | ".join(parts)

    return sanitize(result)
