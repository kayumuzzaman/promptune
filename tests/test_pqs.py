"""Task 7: Prompt Quality Score — tests."""

from __future__ import annotations

from promptune.pqs import PQScore, compute_pqs
from promptune.scorer import DimensionScore, ScoreResult


def _make_score(
    clarity: float = 0.5,
    specificity: float = 0.5,
    context: float = 0.5,
    structure: float = 0.5,
    actionability: float = 0.5,
    completeness: float = 0.5,
    conciseness: float = 0.5,
    total: int = 50,
) -> ScoreResult:
    """Helper to create ScoreResult with controlled scores."""
    return ScoreResult(
        total=total,
        dimensions={
            "clarity": DimensionScore(
                score=clarity,
                max_weight=20,
                signals=[],
                suggestion="Improve clarity",
            ),
            "specificity": DimensionScore(
                score=specificity,
                max_weight=25,
                signals=[],
                suggestion="Add specifics",
            ),
            "context": DimensionScore(
                score=context,
                max_weight=20,
                signals=[],
                suggestion="Add context",
            ),
            "structure": DimensionScore(
                score=structure,
                max_weight=15,
                signals=[],
                suggestion="Add structure",
            ),
            "actionability": DimensionScore(
                score=actionability,
                max_weight=15,
                signals=[],
                suggestion="Make actionable",
            ),
            "completeness": DimensionScore(
                score=completeness,
                max_weight=10,
                signals=[],
                suggestion="Be more complete",
            ),
            "conciseness": DimensionScore(
                score=conciseness,
                max_weight=5,
                signals=[],
                suggestion="Be concise",
            ),
        },
        intent="coding",
    )


def test_compute_pqs_returns_pqscore() -> None:
    """compute_pqs returns a PQScore instance."""
    score = _make_score()
    result = compute_pqs(score)
    assert isinstance(result, PQScore)


def test_pqs_clarity_direct_mapping() -> None:
    """Clarity maps directly from scorer clarity."""
    score = _make_score(clarity=0.8)
    result = compute_pqs(score)
    assert result.clarity.score == 80


def test_pqs_specificity_weighted_avg() -> None:
    """Specificity combines specificity and completeness."""
    score = _make_score(specificity=0.9, completeness=0.6)
    result = compute_pqs(score)
    expected = round((90 * 25 + 60 * 10) / 35)
    assert result.specificity.score == expected


def test_pqs_context_direct_mapping() -> None:
    """Context maps directly from scorer context."""
    score = _make_score(context=0.65)
    result = compute_pqs(score)
    assert result.context.score == 65


def test_pqs_structure_direct_mapping() -> None:
    """Structure maps directly from scorer structure."""
    score = _make_score(structure=0.45)
    result = compute_pqs(score)
    assert result.structure.score == 45


def test_pqs_actionability_weighted_avg() -> None:
    """Actionability combines actionability and conciseness."""
    score = _make_score(actionability=0.7, conciseness=0.9)
    result = compute_pqs(score)
    expected = round((70 * 15 + 90 * 5) / 20)
    assert result.actionability.score == expected


def test_pqs_color_red() -> None:
    """Score 0-39 gets red color."""
    score = _make_score(clarity=0.2)
    result = compute_pqs(score)
    assert result.clarity.color == "red"


def test_pqs_color_yellow() -> None:
    """Score 40-69 gets yellow color."""
    score = _make_score(clarity=0.55)
    result = compute_pqs(score)
    assert result.clarity.color == "yellow"


def test_pqs_color_green() -> None:
    """Score 70-100 gets green color."""
    score = _make_score(clarity=0.85)
    result = compute_pqs(score)
    assert result.clarity.color == "green"


def test_pqs_bar_visualization() -> None:
    """Bar uses unicode blocks proportional to score."""
    score = _make_score(clarity=0.5)
    result = compute_pqs(score)
    assert "\u2588" in result.clarity.bar
    assert "\u2591" in result.clarity.bar
    assert len(result.clarity.bar) == 10


def test_pqs_overall_weighted() -> None:
    """Overall score is weighted composite."""
    score = _make_score(
        clarity=0.8,
        specificity=0.7,
        context=0.6,
        structure=0.5,
        actionability=0.4,
        completeness=0.7,
        conciseness=0.4,
    )
    result = compute_pqs(score)
    assert 0 <= result.overall <= 100


def test_pqs_suggestion_passthrough() -> None:
    """Suggestions come from scorer dimensions."""
    score = _make_score(clarity=0.3)
    result = compute_pqs(score)
    assert result.clarity.suggestion == "Improve clarity"


def test_pqs_zero_scores() -> None:
    """All zero scores produce valid PQScore."""
    score = _make_score(
        clarity=0,
        specificity=0,
        context=0,
        structure=0,
        actionability=0,
        completeness=0,
        conciseness=0,
        total=0,
    )
    result = compute_pqs(score)
    assert result.overall == 0
    assert result.clarity.color == "red"
