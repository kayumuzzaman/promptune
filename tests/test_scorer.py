"""Quality Scorer tests."""

from promptune.scorer import (
    DimensionScore,
    ScoreResult,
    _detect_intent,
    score_prompt,
)


def test_detect_intent_matches_regular_plurals() -> None:
    """Plural coding keywords still count (e.g. 'tests' -> 'test')."""
    assert _detect_intent("write tests") == "coding"
    assert _detect_intent("add api endpoints") == "coding"


def test_detect_intent_matches_verb_inflections() -> None:
    """Scorer shares the inflection-aware matcher (debugging/classes/...)."""
    assert _detect_intent("debugging the parser") == "coding"
    assert _detect_intent("write classes for the model") == "coding"


def test_score_result_dataclass() -> None:
    """ScoreResult has required fields."""
    result = ScoreResult(
        total=50,
        dimensions={"specificity": DimensionScore(
            score=0.5, max_weight=25.0,
            signals=["test"], suggestion="add detail",
        )},
        intent="coding",
    )
    assert result.total == 50
    assert result.intent == "coding"
    assert "specificity" in result.dimensions


def test_dimension_score_dataclass() -> None:
    """DimensionScore has required fields."""
    ds = DimensionScore(
        score=0.7, max_weight=25.0, signals=["term"], suggestion="ok"
    )
    assert ds.score == 0.7
    assert ds.max_weight == 25.0
    assert ds.signals == ["term"]
    assert ds.suggestion == "ok"


def test_score_prompt_returns_score_result() -> None:
    """score_prompt returns a ScoreResult."""
    result = score_prompt("build a REST API with Flask")
    assert isinstance(result, ScoreResult)
    assert 0 <= result.total <= 100
    assert isinstance(result.dimensions, dict)
    assert isinstance(result.intent, str)


def test_score_prompt_has_all_dimensions() -> None:
    """ScoreResult contains all 7 dimensions."""
    result = score_prompt("test prompt")
    expected = {
        "specificity", "clarity", "structure", "actionability",
        "context", "completeness", "conciseness",
    }
    assert set(result.dimensions.keys()) == expected


def test_specificity_high_for_detailed_prompt() -> None:
    """Detailed prompt with technical terms scores high."""
    result = score_prompt(
        "Build a REST API using Flask with SQLAlchemy ORM, PostgreSQL "
        "database, JWT authentication, rate limiting at 100 req/min, "
        "and return JSON responses with proper HTTP status codes"
    )
    spec = result.dimensions["specificity"]
    assert spec.score > 0.5, f"Expected high specificity, got {spec.score}"


def test_specificity_low_for_vague_prompt() -> None:
    """Vague prompt scores low on specificity."""
    result = score_prompt("fix the thing")
    spec = result.dimensions["specificity"]
    assert spec.score < 0.4, f"Expected low specificity, got {spec.score}"


def test_clarity_penalizes_negation() -> None:
    """Prompts with negation score lower on clarity."""
    positive = score_prompt("Use Python 3.12 for this project")
    negative = score_prompt(
        "Don't not use any language other than Python"
    )
    pos_score = positive.dimensions["clarity"].score
    neg_score = negative.dimensions["clarity"].score
    assert pos_score >= neg_score


def test_clarity_constraint_no_more_than_not_penalized() -> None:
    """The constraint phrase 'no more than' is not counted as a negation."""
    result = score_prompt(
        "Return a summary in no more than 100 words using Python"
    )
    signals = result.dimensions["clarity"].signals
    assert not any("negation" in s for s in signals)


def test_structure_detects_markdown() -> None:
    """Prompt with markdown structure scores high."""
    structured = score_prompt(
        "## Task\nBuild an API\n## Requirements\n"
        "- Auth\n- Rate limiting\n## Output\nJSON"
    )
    flat = score_prompt(
        "build an api with auth and rate limiting "
        "that returns json"
    )
    s_score = structured.dimensions["structure"].score
    f_score = flat.dimensions["structure"].score
    assert s_score > f_score


def test_actionability_detects_imperative_verbs() -> None:
    """Prompt with imperative verbs scores higher."""
    actionable = score_prompt(
        "Implement a function that validates email addresses"
    )
    vague = score_prompt("something about email stuff")
    a_score = actionable.dimensions["actionability"].score
    v_score = vague.dimensions["actionability"].score
    assert a_score > v_score


def test_context_detects_role_assignment() -> None:
    """Prompt with role assignment scores higher on context."""
    with_role = score_prompt(
        "You are a senior Python developer. Review this code."
    )
    without_role = score_prompt("Review this code.")
    wr_score = with_role.dimensions["context"].score
    wo_score = without_role.dimensions["context"].score
    assert wr_score > wo_score


def test_completeness_detects_output_format() -> None:
    """Prompt specifying output format scores higher."""
    complete = score_prompt(
        "Build a function. Return a JSON object "
        "with keys: status, data, error."
    )
    incomplete = score_prompt("Build a function")
    c_score = complete.dimensions["completeness"].score
    i_score = incomplete.dimensions["completeness"].score
    assert c_score > i_score


def test_conciseness_penalizes_filler() -> None:
    """Prompt with filler words scores lower on conciseness."""
    concise = score_prompt(
        "Implement JWT authentication for the API endpoint"
    )
    wordy = score_prompt(
        "Could you please kindly help me implement JWT "
        "authentication for the API endpoint if you don't mind?"
    )
    c_score = concise.dimensions["conciseness"].score
    w_score = wordy.dimensions["conciseness"].score
    assert c_score > w_score


def test_intent_detection_coding() -> None:
    """Coding intent detected for programming prompts."""
    result = score_prompt("build a REST API with Flask")
    assert result.intent == "coding"


def test_intent_detection_writing() -> None:
    """Writing intent detected for writing prompts."""
    result = score_prompt(
        "write a blog post about machine learning trends"
    )
    assert result.intent == "writing"


def test_intent_detection_research() -> None:
    """Research intent detected for research prompts."""
    result = score_prompt("explain how DNS resolution works")
    assert result.intent == "research"


def test_detect_intent_matches_meta_prompt_for_drifted_keywords() -> None:
    """scorer intent must agree with meta_prompt for coding keywords that the
    old duplicate list was missing (application/program/tool/library/package/
    migrate)."""
    from promptune.meta_prompt import detect_intent

    for prompt in (
        "migrate the application to a new library",
        "publish the package as a CLI program",
        "build a tool for the team",
    ):
        assert _detect_intent(prompt) == "coding"
        assert detect_intent(prompt) == _detect_intent(prompt)


def test_intent_detection_ignores_substring_matches() -> None:
    """Keywords match whole words, not substrings (api vs capital)."""
    result = score_prompt(
        "write an essay about capital punishment for my blog"
    )
    assert result.intent == "writing"


def test_context_score_ignores_substring_tech_terms() -> None:
    """Context domain keywords match whole words, not substrings."""
    result = score_prompt(
        "write an essay about capital punishment in a restaurant"
    )

    context = result.dimensions["context"]
    assert not any("domain keywords" in signal for signal in context.signals)


def test_score_calibration_prevents_clustering() -> None:
    """Scores should span a reasonable range, not cluster."""
    prompts = [
        "fix it",
        "fix the bug in the auth module",
        (
            "## Task\nFix the authentication bug in "
            "src/auth/redirect.ts\n"
            "## Context\nYou are a TypeScript expert. "
            "The redirect after "
            "OAuth login fails with a TypeError.\n"
            "## Requirements\n"
            "- Preserve existing test coverage\n"
            "- Add error handling\n"
            "## Output\nReturn the corrected code "
            "with inline comments"
        ),
    ]
    scores = [score_prompt(p).total for p in prompts]
    score_range = max(scores) - min(scores)
    assert score_range >= 30, f"Scores too clustered: {scores}"


def test_score_total_is_calibrated_integer() -> None:
    """Total score is an integer 0-100."""
    result = score_prompt("build a REST API")
    assert isinstance(result.total, int)
    assert 0 <= result.total <= 100


def test_dimension_scores_have_suggestions() -> None:
    """Each dimension provides an actionable suggestion."""
    result = score_prompt("fix it")
    for name, dim in result.dimensions.items():
        assert isinstance(dim.suggestion, str), (
            f"{name} missing suggestion"
        )
        assert len(dim.suggestion) > 0, (
            f"{name} has empty suggestion"
        )


def test_scorer_performance() -> None:
    """Scorer runs in <50ms for typical prompts."""
    import time
    prompt = "Build a REST API using Flask with JWT authentication"
    start = time.perf_counter()
    for _ in range(100):
        score_prompt(prompt)
    elapsed_ms = (time.perf_counter() - start) * 1000
    avg_ms = elapsed_ms / 100
    assert avg_ms < 50, f"Scorer too slow: {avg_ms:.1f}ms avg"


def test_empty_string_input() -> None:
    """Empty string returns valid ScoreResult with low score."""
    result = score_prompt("")
    assert isinstance(result, ScoreResult)
    assert result.total >= 0
    assert result.total <= 100


def test_general_intent_fallback() -> None:
    """Prompt with no intent keywords returns 'general' intent."""
    result = score_prompt("hello world")
    assert result.intent == "general"


def test_intent_weight_adjustment_affects_scores() -> None:
    """Coding intent should slightly boost specificity weight."""
    result = score_prompt("implement the REST API endpoint")
    assert result.intent == "coding"
    assert 0 <= result.total <= 100


def test_structure_score_ignores_generics_as_xml() -> None:
    """Generics/comparisons must not be counted as structural XML tags."""
    from promptune.scorer import _score_structure

    dim = _score_structure("implement vector<int> and Map<K> please")
    assert not any("XML" in s for s in dim.signals)


def test_structure_score_counts_real_xml_tags() -> None:
    from promptune.scorer import _score_structure

    dim = _score_structure("use <task> and <context> sections")
    assert any("XML tag" in s for s in dim.signals)
