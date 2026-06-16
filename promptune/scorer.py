"""Quality Scorer: 7-dimension heuristic prompt scoring (0-100).

Research basis:
- Bsharat et al. 2023: 26 validated principles — specificity is strongest predictor
- Schulhoff et al. 2024 "The Prompt Report": structure > word choice
- DETAIL paper (arXiv:2512.02246): specificity +0.47 on procedural tasks
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from promptune.meta_prompt import _keyword_matches


@dataclass
class DimensionScore:
    """Score for a single dimension."""

    score: float          # 0-1 raw
    max_weight: float     # dimension weight
    signals: list[str]    # what was detected
    suggestion: str       # actionable fix


@dataclass
class ScoreResult:
    """Result of scoring a prompt."""

    total: int                              # 0-100 calibrated
    dimensions: dict[str, DimensionScore]   # per-dimension detail
    intent: str                             # detected prompt type


# --- Intent detection (reuses meta_prompt logic) ---

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "coding": [
        "build", "create", "implement", "code", "develop", "api",
        "function", "class", "app", "script", "debug", "fix",
        "refactor", "deploy", "test", "endpoint", "database",
        "server", "cli", "component", "module", "service",
    ],
    "writing": [
        "write", "draft", "compose", "essay", "blog", "article",
        "email", "letter", "story", "post", "content", "copy",
        "documentation", "report", "proposal", "summary",
    ],
    "research": [
        "explain", "describe", "what is", "how does", "why",
        "compare", "analyze", "evaluate", "review", "understand",
        "difference between", "overview", "summarize",
    ],
}


def _detect_intent(prompt: str) -> str:
    """Detect prompt intent: coding, writing, research, or general."""
    lower = prompt.lower()
    scores: dict[str, int] = {k: 0 for k in _INTENT_KEYWORDS}
    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            # Shared matcher accepts inflections ("tests", "debugging", ...).
            if _keyword_matches(lower, kw):
                scores[intent] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


# --- Scoring curves ---

def _diminishing_returns(
    raw_count: int, max_points: float, k: float = 0.5
) -> float:
    """Exponential decay for diminishing returns."""
    return max_points * (1 - math.exp(-k * raw_count))


def _sigmoid_calibrate(
    raw: float, midpoint: float = 50.0, steepness: float = 0.08
) -> float:
    """Sigmoid calibration (rescaled so raw 0->0 and raw 100->100)."""
    def _sig(x: float) -> float:
        return 100.0 / (1 + math.exp(-steepness * (x - midpoint)))

    lo, hi = _sig(0.0), _sig(100.0)
    return (_sig(raw) - lo) / (hi - lo) * 100.0


# --- Word sets ---

_VAGUE_WORDS = {
    "thing", "things", "stuff", "something", "anything", "everything",
    "good", "bad", "nice", "great", "better", "best", "some", "many",
    "very", "really", "quite", "basically", "kind of", "sort of",
}

_TECH_TERMS = {
    "api", "rest", "graphql", "sql", "jwt", "oauth", "tcp", "http",
    "json", "xml", "yaml", "docker", "kubernetes", "redis", "postgresql",
    "mongodb", "aws", "gcp", "azure", "typescript", "python", "rust",
    "flask", "django", "react", "nextjs", "node", "express",
}

_CONSTRAINT_MARKERS = [
    "must", "should", "require", "constraint", "limit", "maximum",
    "minimum", "at least", "at most", "no more than", "between",
]

_PRECISE_VERBS = {
    "implement", "create", "build", "configure", "deploy", "migrate",
    "refactor", "optimize", "validate", "authenticate", "serialize",
    "parse", "render", "transform", "aggregate", "filter", "map",
}

_VAGUE_VERBS = {
    "do", "make", "get", "put", "handle", "process", "deal with",
    "take care of", "work on", "look at", "check", "help",
}

_FILLER_WORDS = {
    "please", "kindly", "just", "maybe", "perhaps", "i think",
    "could you", "would you", "if possible", "if you don't mind",
    "i was wondering", "it would be great",
}


# --- Helpers ---

def _shannon_entropy(words: list[str]) -> float:
    """Calculate Shannon entropy (word-level)."""
    if not words:
        return 0.0
    freq: dict[str, int] = {}
    for w in words:
        lower = w.lower()
        freq[lower] = freq.get(lower, 0) + 1
    n = len(words)
    entropy = 0.0
    for count in freq.values():
        p = count / n
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def _count_syllables(word: str) -> int:
    """Approximate syllable count for Flesch-Kincaid."""
    word = word.lower().rstrip("e")
    vowels = "aeiou"
    count = 0
    prev_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    return max(count, 1)


def _flesch_kincaid_grade(
    words: list[str], num_sentences: int
) -> float:
    """Compute Flesch-Kincaid grade level."""
    if not words or num_sentences == 0:
        return 0.0
    avg_sentence_len = len(words) / num_sentences
    total_syllables = sum(_count_syllables(w) for w in words)
    avg_syllables = total_syllables / max(len(words), 1)
    grade = 0.39 * avg_sentence_len + 11.8 * avg_syllables - 15.59
    return max(0.0, grade)


# --- Dimension scorers ---

def _score_specificity(
    prompt: str, words: list[str]
) -> DimensionScore:
    """Score specificity: entropy, TTR, tech terms, vague penalties."""
    signals: list[str] = []

    entropy = _shannon_entropy(words)
    entropy_score = min(entropy / 5.0, 1.0)
    if entropy > 3.5:
        signals.append(
            f"high information density (entropy={entropy:.2f})"
        )

    unique = set(w.lower() for w in words)
    ttr = len(unique) / max(len(words), 1)
    ttr_score = min(ttr, 1.0)
    if ttr > 0.7:
        signals.append(f"high vocabulary diversity (TTR={ttr:.2f})")

    lower_words = {w.lower() for w in words}
    tech_count = len(lower_words & _TECH_TERMS)
    tech_score = _diminishing_returns(tech_count, 1.0, k=0.3)
    if tech_count > 0:
        signals.append(f"{tech_count} technical terms")

    vague_count = sum(1 for v in _VAGUE_WORDS if v in prompt.lower())
    vague_penalty = min(vague_count * 0.1, 0.5)
    if vague_count > 0:
        signals.append(f"{vague_count} vague words")

    constraint_count = sum(
        1 for c in _CONSTRAINT_MARKERS if c in prompt.lower()
    )
    constraint_score = _diminishing_returns(
        constraint_count, 1.0, k=0.4
    )
    if constraint_count > 0:
        signals.append(f"{constraint_count} constraint markers")

    numbers = len(re.findall(r'\d+', prompt))
    number_score = _diminishing_returns(numbers, 0.5, k=0.3)
    if numbers > 0:
        signals.append(f"{numbers} numeric values")

    raw = (
        entropy_score * 0.2
        + ttr_score * 0.15
        + tech_score * 0.25
        + constraint_score * 0.2
        + number_score * 0.1
        - vague_penalty
        + 0.1
    )
    raw = max(0.0, min(1.0, raw))

    suggestion = (
        "Add specific technical terms, constraints, or numeric values"
        if raw < 0.5
        else "Good specificity"
    )
    return DimensionScore(
        score=raw, max_weight=25.0, signals=signals, suggestion=suggestion
    )


def _score_clarity(
    prompt: str, words: list[str]
) -> DimensionScore:
    """Score clarity: FK readability, negation, ambiguous pronouns."""
    signals: list[str] = []

    sentences = [
        s.strip() for s in re.split(r'[.!?\n]', prompt) if s.strip()
    ]
    num_sentences = max(len(sentences), 1)

    fk_grade = _flesch_kincaid_grade(words, num_sentences)
    if 8 <= fk_grade <= 14:
        length_score = 1.0
        signals.append(f"ideal readability (FK grade {fk_grade:.1f})")
    elif fk_grade < 4:
        length_score = 0.3
        signals.append(f"too simple (FK grade {fk_grade:.1f})")
    elif fk_grade > 18:
        length_score = 0.3
        signals.append(f"too complex (FK grade {fk_grade:.1f})")
    else:
        length_score = max(0.3, 1.0 - abs(fk_grade - 11) / 15)
        signals.append(f"FK grade {fk_grade:.1f}")

    negations = len(
        re.findall(
            r"\bdon'?t\b|\bnot\b|\bnever\b"
            r"|\bno\b(?!\s+(?:more|less|fewer|longer)\b)|\bnor\b",
            prompt.lower(),
        )
    )
    neg_penalty = min(negations * 0.15, 0.5)
    if negations > 0:
        signals.append(f"{negations} negations")

    ambiguous = len(
        re.findall(r'\b(it|this|that|they|them)\b', prompt.lower())
    )
    ambig_ratio = ambiguous / max(len(words), 1)
    ambig_penalty = min(ambig_ratio * 2, 0.3)
    if ambiguous > 2:
        signals.append(f"{ambiguous} ambiguous pronouns")

    raw = length_score - neg_penalty - ambig_penalty
    raw = max(0.0, min(1.0, raw))

    suggestion = (
        "Use affirmative directives instead of negation; "
        "reduce ambiguous pronouns"
        if raw < 0.5
        else "Good clarity"
    )
    return DimensionScore(
        score=raw, max_weight=20.0, signals=signals, suggestion=suggestion
    )


def _score_structure(prompt: str) -> DimensionScore:
    """Score structure: delimiters, lists, code blocks, sections."""
    signals: list[str] = []
    markers = 0

    headers = len(re.findall(r'^#{1,6}\s', prompt, re.MULTILINE))
    if headers > 0:
        markers += headers
        signals.append(f"{headers} markdown headers")

    lists = len(
        re.findall(
            r'^[\s]*[-*\u2022]\s|^\s*\d+[.)]\s', prompt, re.MULTILINE
        )
    )
    if lists > 0:
        markers += lists
        signals.append(f"{lists} list items")

    code_blocks = len(re.findall(r'```', prompt)) // 2
    if code_blocks > 0:
        markers += code_blocks
        signals.append("code blocks")

    xml_tags = len(re.findall(r'<\w+>', prompt))
    if xml_tags > 0:
        markers += xml_tags
        signals.append(f"{xml_tags} XML tags")

    separators = len(
        re.findall(r'^---+$|^===+$', prompt, re.MULTILINE)
    )
    if separators > 0:
        markers += separators
        signals.append("section separators")

    raw = _diminishing_returns(markers, 1.0, k=0.4)

    suggestion = (
        "Add structure: use headers (##), bullet lists (-), "
        "or labeled sections"
        if raw < 0.3
        else "Good structure"
    )
    return DimensionScore(
        score=raw, max_weight=15.0, signals=signals, suggestion=suggestion
    )


def _score_actionability(
    prompt: str, words: list[str]
) -> DimensionScore:
    """Score actionability: imperative verbs, task clarity."""
    signals: list[str] = []

    lower_words = {w.lower() for w in words}

    precise_count = len(lower_words & _PRECISE_VERBS)
    if precise_count > 0:
        signals.append(f"{precise_count} precise verbs")

    vague_verb_count = sum(
        1 for v in _VAGUE_VERBS if v in prompt.lower()
    )
    if vague_verb_count > 0:
        signals.append(f"{vague_verb_count} vague verbs")

    steps = len(
        re.findall(
            r'\b(step \d|first|then|next|finally|after that)\b',
            prompt.lower(),
        )
    )
    if steps > 0:
        signals.append(f"{steps} step indicators")

    verb_score = _diminishing_returns(precise_count, 1.0, k=0.5)
    vague_penalty = min(vague_verb_count * 0.15, 0.4)
    step_bonus = _diminishing_returns(steps, 0.3, k=0.5)

    raw = verb_score - vague_penalty + step_bonus
    raw = max(0.0, min(1.0, raw))

    suggestion = (
        "Use specific imperative verbs (implement, create, validate) "
        "instead of vague ones (do, make, handle)"
        if raw < 0.4
        else "Good actionability"
    )
    return DimensionScore(
        score=raw, max_weight=15.0, signals=signals, suggestion=suggestion
    )


def _score_context(prompt: str) -> DimensionScore:
    """Score context: role assignment, audience, domain keywords."""
    signals: list[str] = []
    score = 0.0

    if re.search(r'\b(you are|act as|role:)\b', prompt.lower()):
        score += 0.4
        signals.append("role assignment")

    if re.search(
        r'\b(audience|for (beginners|experts|developers|users))\b',
        prompt.lower(),
    ):
        score += 0.2
        signals.append("audience specified")

    lower = prompt.lower()
    domain_count = sum(1 for t in _TECH_TERMS if t in lower)
    domain_bonus = _diminishing_returns(domain_count, 0.3, k=0.3)
    score += domain_bonus
    if domain_count > 0:
        signals.append(f"{domain_count} domain keywords")

    if re.search(r'\b(background|context|given that|assuming)\b', lower):
        score += 0.1
        signals.append("background context")

    raw = min(1.0, score)

    suggestion = (
        "Add role assignment ('You are a...') and domain context"
        if raw < 0.3
        else "Good context"
    )
    return DimensionScore(
        score=raw, max_weight=10.0, signals=signals, suggestion=suggestion
    )


def _score_completeness(prompt: str) -> DimensionScore:
    """Score completeness: output format, examples, success criteria."""
    signals: list[str] = []
    score = 0.0

    lower = prompt.lower()

    if re.search(
        r'\b(output|return|format|respond)\b.*'
        r'\b(json|xml|csv|table|list|markdown)\b',
        lower,
        re.DOTALL,
    ):
        score += 0.35
        signals.append("output format specified")

    if re.search(r'\b(example|e\.g\.|for instance|such as)\b', lower):
        score += 0.25
        signals.append("examples included")

    if re.search(
        r'\b(success|criteria|acceptance|expect|'
        r'should produce|must return)\b',
        lower,
    ):
        score += 0.2
        signals.append("success criteria")

    constraint_count = sum(
        1 for c in _CONSTRAINT_MARKERS if c in lower
    )
    if constraint_count > 0:
        score += _diminishing_returns(constraint_count, 0.2, k=0.4)
        signals.append(f"{constraint_count} constraints")

    raw = min(1.0, score)

    suggestion = (
        "Specify expected output format and include success criteria"
        if raw < 0.3
        else "Good completeness"
    )
    return DimensionScore(
        score=raw, max_weight=10.0, signals=signals, suggestion=suggestion
    )


def _score_conciseness(
    prompt: str, words: list[str]
) -> DimensionScore:
    """Score conciseness: entropy density, filler penalty."""
    signals: list[str] = []

    entropy = _shannon_entropy(words)
    entropy_score = min(entropy / 4.5, 1.0) if words else 0.0
    if entropy > 3.5:
        signals.append(f"dense vocabulary (entropy={entropy:.2f})")

    lower = prompt.lower()
    filler_count = sum(1 for f in _FILLER_WORDS if f in lower)
    filler_penalty = min(filler_count * 0.15, 0.6)
    if filler_count > 0:
        signals.append(f"{filler_count} filler/politeness phrases")

    word_count = len(words)
    filler_ratio = filler_count / max(word_count, 1)
    ratio_penalty = min(filler_ratio * 2, 0.3)

    raw = entropy_score * 0.5 + 0.5 - filler_penalty - ratio_penalty
    raw = max(0.0, min(1.0, raw))

    suggestion = (
        "Remove filler words (please, kindly, just) — "
        "they reduce prompt effectiveness"
        if raw < 0.5
        else "Good conciseness"
    )
    return DimensionScore(
        score=raw, max_weight=5.0, signals=signals, suggestion=suggestion
    )


# --- Intent-aware weight adjustment ---

_INTENT_WEIGHT_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "coding": {"specificity": 0.05, "actionability": 0.03},
    "writing": {"specificity": -0.05, "clarity": 0.05},
    "research": {"context": 0.05, "actionability": -0.03},
}


# --- Main scoring function ---

def score_prompt(prompt: str) -> ScoreResult:
    """Score a prompt across 7 dimensions, returning calibrated 0-100."""
    words = prompt.split()
    intent = _detect_intent(prompt)

    dimensions: dict[str, DimensionScore] = {
        "specificity": _score_specificity(prompt, words),
        "clarity": _score_clarity(prompt, words),
        "structure": _score_structure(prompt),
        "actionability": _score_actionability(prompt, words),
        "context": _score_context(prompt),
        "completeness": _score_completeness(prompt),
        "conciseness": _score_conciseness(prompt, words),
    }

    raw_total = 0.0
    max_total = 0.0
    for name, dim in dimensions.items():
        weight = dim.max_weight
        adjustment = _INTENT_WEIGHT_ADJUSTMENTS.get(
            intent, {}
        ).get(name, 0.0)
        adjusted_weight = weight * (1 + adjustment)
        raw_total += dim.score * adjusted_weight
        max_total += adjusted_weight

    raw_score = (raw_total / max(max_total, 1)) * 100
    calibrated = _sigmoid_calibrate(raw_score)
    total = max(0, min(100, round(calibrated)))

    return ScoreResult(
        total=total, dimensions=dimensions, intent=intent
    )
