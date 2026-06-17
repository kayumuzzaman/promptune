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
) -> DedupHit | None:
    """Check if a similar prompt was recently enhanced.

    Returns DedupHit if a match is found above threshold,
    None otherwise. Skips prompts shorter than 3 words.
    """
    tokens = tokenize(prompt)
    if len(tokens) < 3:
        return None

    entries = store.recent(n=window, project=project_root)

    best_score = 0.0
    best_enhanced: str | None = None
    best_original: str | None = None

    for entry in entries:
        if entry.decision == "reject":
            continue

        sim = cosine_similarity(prompt, entry.original)
        if sim > best_score:
            best_score = sim
            best_original = entry.original
            if entry.decision == "edit" and entry.edit_result:
                best_enhanced = entry.edit_result
            else:
                best_enhanced = entry.enhanced

    if best_score >= threshold and best_enhanced:
        return DedupHit(
            enhanced=best_enhanced,
            similarity=best_score,
            original_prompt=best_original or "",
        )

    return None
