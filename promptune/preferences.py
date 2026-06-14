"""Preference learning — analyse history to adapt enhancements."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from promptune.history import HistoryStore


@dataclass
class Preference:
    """A learned preference about a Tier 0 rule."""

    rule_name: str
    action: str  # "skip" or "keep"
    confidence: float  # 0.0-1.0
    sample_count: int


@dataclass
class EditPattern:
    """A detected edit pattern from user history."""

    pattern_type: str  # "removes_role", "removes_format"
    description: str
    frequency: float  # 0.0-1.0
    sample_count: int


_ROLE_PREFIXES = re.compile(
    r"^You are (?:a |an )?[\w\s]+\.\s*",
    re.IGNORECASE,
)
_FORMAT_SUFFIXES = re.compile(
    r"\n\n(?:Respond |Structure |Provide )[\w\s]+\.\s*$",
    re.IGNORECASE,
)


def analyse_rule_preferences(
    store: HistoryStore,
    min_samples: int = 5,
    project: str | None = None,
) -> list[Preference]:
    """Analyse history to learn rule accept/reject patterns."""
    entries = store.recent(n=10000, project=project)

    rule_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"accept": 0, "reject": 0}
    )

    for entry in entries:
        if not entry.rules_applied:
            continue
        if entry.decision not in ("accept", "reject"):
            continue
        for rule in entry.rules_applied:
            rule_stats[rule][entry.decision] += 1

    preferences: list[Preference] = []

    for rule_name, counts in rule_stats.items():
        total = counts["accept"] + counts["reject"]
        if total < min_samples:
            continue

        reject_rate = counts["reject"] / total
        accept_rate = counts["accept"] / total

        if reject_rate > 0.6:
            preferences.append(Preference(
                rule_name=rule_name,
                action="skip",
                confidence=reject_rate,
                sample_count=total,
            ))
        elif accept_rate > 0.6:
            preferences.append(Preference(
                rule_name=rule_name,
                action="keep",
                confidence=accept_rate,
                sample_count=total,
            ))

    return preferences


def analyse_edit_patterns(
    store: HistoryStore,
    min_samples: int = 5,
    project: str | None = None,
) -> list[EditPattern]:
    """Analyse edit history to find repeated removal patterns."""
    entries = store.recent(n=10000, project=project)

    edits = [
        e for e in entries
        if e.decision == "edit" and e.edit_result is not None
    ]

    if len(edits) < min_samples:
        return []

    removes_role = 0
    removes_format = 0

    for entry in edits:
        enhanced = entry.enhanced
        edited = entry.edit_result or ""

        if _ROLE_PREFIXES.search(enhanced) and not _ROLE_PREFIXES.search(edited):
            removes_role += 1

        if _FORMAT_SUFFIXES.search(enhanced) and not _FORMAT_SUFFIXES.search(edited):
            removes_format += 1

    total = len(edits)
    patterns: list[EditPattern] = []

    if removes_role / total > 0.6:
        patterns.append(EditPattern(
            pattern_type="removes_role",
            description="User consistently removes role assignment",
            frequency=removes_role / total,
            sample_count=total,
        ))

    if removes_format / total > 0.6:
        patterns.append(EditPattern(
            pattern_type="removes_format",
            description="User consistently removes output format instructions",
            frequency=removes_format / total,
            sample_count=total,
        ))

    return patterns
