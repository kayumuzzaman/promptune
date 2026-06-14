"""Prompt Quality Score — user-facing 5-dimension display."""

from __future__ import annotations

from dataclasses import dataclass

from promptune.scorer import ScoreResult


@dataclass
class DimensionDisplay:
    """Single PQS dimension for display."""

    score: int
    color: str
    bar: str
    suggestion: str


@dataclass
class PQScore:
    """Full prompt quality score for TUI display."""

    clarity: DimensionDisplay
    specificity: DimensionDisplay
    context: DimensionDisplay
    structure: DimensionDisplay
    actionability: DimensionDisplay
    overall: int


def _score_to_color(score: int) -> str:
    """Map score to color band."""
    if score < 40:
        return "red"
    if score < 70:
        return "yellow"
    return "green"


def _score_to_bar(score: int, width: int = 10) -> str:
    """Create unicode block bar visualization."""
    filled = round(score / 100 * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def _make_dimension(
    score: int, suggestion: str
) -> DimensionDisplay:
    """Create a DimensionDisplay from score."""
    clamped = max(0, min(100, score))
    return DimensionDisplay(
        score=clamped,
        color=_score_to_color(clamped),
        bar=_score_to_bar(clamped),
        suggestion=suggestion,
    )


def compute_pqs(score_result: ScoreResult) -> PQScore:
    """Compute PQS from scorer internals.

    Mapping (from spec Section 7):
    - Clarity: direct from scorer clarity
    - Specificity: weighted avg of specificity + completeness
    - Context: direct from scorer context
    - Structure: direct from scorer structure
    - Actionability: weighted avg of actionability + conciseness
    """
    d = score_result.dimensions

    clarity_raw = round(d["clarity"].score * 100)
    spec_raw = round(d["specificity"].score * 100)
    comp_raw = round(d["completeness"].score * 100)
    ctx_raw = round(d["context"].score * 100)
    struct_raw = round(d["structure"].score * 100)
    act_raw = round(d["actionability"].score * 100)
    conc_raw = round(d["conciseness"].score * 100)

    clarity_score = clarity_raw
    specificity_score = round(
        (spec_raw * 25 + comp_raw * 10) / 35
    )
    context_score = ctx_raw
    structure_score = struct_raw
    actionability_score = round(
        (act_raw * 15 + conc_raw * 5) / 20
    )

    clarity = _make_dimension(
        clarity_score, d["clarity"].suggestion
    )
    specificity = _make_dimension(
        specificity_score, d["specificity"].suggestion
    )
    context = _make_dimension(
        context_score, d["context"].suggestion
    )
    structure = _make_dimension(
        structure_score, d["structure"].suggestion
    )
    actionability = _make_dimension(
        actionability_score, d["actionability"].suggestion
    )

    overall = round(
        clarity_score * 0.25
        + specificity_score * 0.25
        + context_score * 0.20
        + structure_score * 0.15
        + actionability_score * 0.15
    )

    return PQScore(
        clarity=clarity,
        specificity=specificity,
        context=context,
        structure=structure,
        actionability=actionability,
        overall=overall,
    )
