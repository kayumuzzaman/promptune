"""Semantic deduplication — term-frequency cosine similarity (stdlib only)."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from promptune.history import HistoryStore


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return cleaned.split()


def _term_freq(tokens: list[str]) -> dict[str, float]:
    """Compute term frequency (TF) for a token list."""
    counts = Counter(tokens)
    total = len(tokens)
    if total == 0:
        return {}
    return {t: c / total for t, c in counts.items()}


def cosine_similarity(text_a: str, text_b: str) -> float:
    """Compute TF-based cosine similarity between two texts."""
    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)

    if not tokens_a or not tokens_b:
        return 0.0

    tf_a = _term_freq(tokens_a)
    tf_b = _term_freq(tokens_b)

    all_terms = set(tf_a) | set(tf_b)

    dot = sum(tf_a.get(t, 0.0) * tf_b.get(t, 0.0) for t in all_terms)

    mag_a = math.sqrt(sum(v * v for v in tf_a.values()))
    mag_b = math.sqrt(sum(v * v for v in tf_b.values()))

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return dot / (mag_a * mag_b)


@dataclass
class DedupHit:
    """Result when dedup finds a cached match."""

    enhanced: str
    similarity: float
    original_prompt: str


def dedup_check(
    prompt: str,
    project_root: str,
    store: HistoryStore,
    threshold: float = 0.85,
    window: int = 50,
    format_style: str | None = None,
) -> DedupHit | None:
    """Check if a similar prompt was recently enhanced.

    Returns DedupHit if a match is found above threshold,
    None otherwise. Skips prompts shorter than 3 words.

    When *format_style* is given, only entries produced with the same format are
    considered — a cached result in another format wouldn't honour the current
    request. Pass ``None`` to match regardless of format.
    """
    tokens = tokenize(prompt)
    if len(tokens) < 3:
        return None

    entries = store.recent(n=window, project=project_root)

    best_score = 0.0
    best_enhanced: str | None = None
    best_original: str | None = None
    best_is_edit = False

    for entry in entries:
        if entry.decision == "reject":
            continue
        if format_style is not None and entry.format_style != format_style:
            continue

        sim = cosine_similarity(prompt, entry.original)
        is_edit = entry.decision == "edit" and bool(entry.edit_result)
        # On an exact-similarity tie, prefer a user-edited result over a plain
        # accept — the edit reflects what the user actually wanted.
        if sim > best_score or (
            sim == best_score and is_edit and not best_is_edit
        ):
            best_score = sim
            best_original = entry.original
            best_enhanced = entry.edit_result if is_edit else entry.enhanced
            best_is_edit = is_edit

    if best_score >= threshold and best_enhanced:
        return DedupHit(
            enhanced=best_enhanced,
            similarity=best_score,
            original_prompt=best_original or "",
        )

    return None
