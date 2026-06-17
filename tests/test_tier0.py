"""Tier 0 Rule Engine tests."""

from promptune.scorer import DimensionScore, ScoreResult, score_prompt
from promptune.tier0 import (
    RuleResult,
    Tier0Result,
    apply_rules,
    rule_politeness_removal,
)


def _low_conciseness_score() -> ScoreResult:
    """Build a ScoreResult that forces the politeness rule to fire."""
    return ScoreResult(
        total=30,
        dimensions={
            "conciseness": DimensionScore(
                score=0.2, max_weight=5.0, signals=[], suggestion=""
            )
        },
        intent="general",
    )


def test_politeness_removal_preserves_words_containing_phrases() -> None:
    """Must strip standalone politeness words, not substrings inside words."""
    score = _low_conciseness_score()
    result = rule_politeness_removal(
        "please make the user pleased", score
    )
    assert result.applied is True
    # standalone 'please' removed, but 'pleased' must survive intact
    assert "pleased" in result.modified_prompt


def test_politeness_removal_no_orphan_punctuation() -> None:
    """Removing a trailing politeness phrase must not leave stray punctuation."""
    score = _low_conciseness_score()
    # trailing 'please' after a comma — must not leave a dangling comma
    r1 = rule_politeness_removal("build the parser, please", score)
    assert r1.modified_prompt == "build the parser"
    # phrase-only input must not leave an orphan '!'
    r2 = rule_politeness_removal("please!", score)
    assert r2.modified_prompt == ""
    # phrase between a comma and a period must not leave doubled punctuation
    r3 = rule_politeness_removal("fix the parser, please.", score)
    assert r3.modified_prompt == "fix the parser."
    # sentence-final '?' must survive when the phrase is leading
    r4 = rule_politeness_removal(
        "could you please explain recursion?", score
    )
    assert r4.modified_prompt == "explain recursion?"


def test_rule_result_dataclass() -> None:
    """RuleResult has required fields."""
    rr = RuleResult(
        modified_prompt="test", applied=True, description="did thing"
    )
    assert rr.modified_prompt == "test"
    assert rr.applied is True
    assert rr.description == "did thing"


def test_tier0_result_dataclass() -> None:
    """Tier0Result has required fields."""
    tr = Tier0Result(
        enhanced="enhanced text",
        rules_applied=["rule_a"],
        rules_explained=[("rule_a", "Did something")],
    )
    assert tr.enhanced == "enhanced text"
    assert tr.rules_applied == ["rule_a"]


def test_tier0_result_has_rules_explained() -> None:
    """Tier0Result has rules_explained field."""
    tr = Tier0Result(
        enhanced="text",
        rules_applied=["vague_verbs"],
        rules_explained=[("vague_verbs", "Replaced vague verbs")],
    )
    assert tr.rules_explained == [
        ("vague_verbs", "Replaced vague verbs")
    ]


def test_apply_rules_populates_rules_explained() -> None:
    """apply_rules populates rules_explained with descriptions."""
    score = score_prompt("make a todo app")
    result = apply_rules("make a todo app", score)
    assert isinstance(result.rules_explained, list)
    for name, desc in result.rules_explained:
        assert isinstance(name, str)
        assert isinstance(desc, str)
        assert len(desc) > 0
    # Every applied rule should have an explanation
    explained_names = [n for n, _ in result.rules_explained]
    assert explained_names == result.rules_applied


def test_apply_rules_returns_tier0_result() -> None:
    """apply_rules returns a Tier0Result."""
    score = score_prompt("fix it")
    result = apply_rules("fix it", score)
    assert isinstance(result, Tier0Result)
    assert isinstance(result.enhanced, str)
    assert isinstance(result.rules_applied, list)


def test_apply_rules_preserves_original_when_high_score() -> None:
    """High-scoring prompts get minimal rule application."""
    detailed = (
        "## Task\nYou are a senior Python developer. "
        "Implement a REST API "
        "using Flask with SQLAlchemy ORM and PostgreSQL.\n"
        "## Requirements\n"
        "- JWT authentication\n"
        "- Rate limiting at 100 req/min\n"
        "## Output\nReturn JSON with proper HTTP status codes"
    )
    score = score_prompt(detailed)
    result = apply_rules(detailed, score)
    assert (
        detailed in result.enhanced
        or len(result.rules_applied) <= 2
    )


def test_rule_add_output_format() -> None:
    """Appends format instruction when completeness is low."""
    score = score_prompt("build a REST API")
    result = apply_rules("build a REST API", score)
    assert "output_format" in result.rules_applied
    assert (
        "format" in result.enhanced.lower()
        or "respond" in result.enhanced.lower()
    )


def test_rule_flag_vague_verbs() -> None:
    """Flags vague verbs with specific alternatives."""
    score = score_prompt("do something with the database")
    result = apply_rules("do something with the database", score)
    assert "vague_verbs" in result.rules_applied
    assert result.enhanced != "do something with the database"


def test_rule_too_short() -> None:
    """Flags very short prompts when specificity near zero."""
    score = score_prompt("fix bug")
    result = apply_rules("fix bug", score)
    assert "too_short" in result.rules_applied
    assert (
        "context" in result.enhanced.lower()
        or "detail" in result.enhanced.lower()
    )


def test_rule_add_constraints() -> None:
    """Appends constraints when completeness is low."""
    score = score_prompt("create a web app")
    result = apply_rules("create a web app", score)
    assert "constraints" in result.rules_applied
    assert len(result.enhanced) > len("create a web app")


def test_rule_negation_rewrite() -> None:
    """Rewrites negative directives to positive."""
    import re as _re
    prompt = (
        "Don't use any global variables "
        "and don't forget error handling"
    )
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "negation_rewrite" in result.rules_applied
    original_negs = len(
        _re.findall(
            r"\bdon'?t\b|\bnot\b|\bnever\b", prompt.lower()
        )
    )
    result_negs = len(
        _re.findall(
            r"\bdon'?t\b|\bnot\b|\bnever\b",
            result.enhanced.lower(),
        )
    )
    assert result_negs <= original_negs


def test_rule_negation_rewrite_spaced_do_not_use() -> None:
    """'do not use' rewrites to 'avoid using', not the ungrammatical 'avoid use'."""
    prompt = "Do not use global variables in the auth module please"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "avoid using" in result.enhanced.lower()
    assert "avoid use " not in result.enhanced.lower()


def test_rule_negation_rewrite_spaced_do_not_forget() -> None:
    """'do not forget' rewrites to 'remember to', not 'avoid forget'."""
    prompt = "Do not forget to add error handling in the auth module"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "remember to" in result.enhanced.lower()
    assert "avoid forget" not in result.enhanced.lower()


def test_rule_negation_rewrite_spaced_do_not_ignore() -> None:
    """'do not ignore' rewrites to 'pay attention to', not 'avoid ignore'."""
    prompt = "Do not ignore the edge cases when you write the parser"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "pay attention to" in result.enhanced.lower()
    assert "avoid ignore" not in result.enhanced.lower()


def test_rule_add_role() -> None:
    """Prepends role when context score is low."""
    score = score_prompt(
        "write unit tests for the auth module"
    )
    result = apply_rules(
        "write unit tests for the auth module", score
    )
    assert "role_assignment" in result.rules_applied
    assert "you are" in result.enhanced.lower()


def test_rule_code_delimiters() -> None:
    """Wraps code-like content in code blocks."""
    prompt = "Fix this: def foo(): return bar"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "code_delimiters" in result.rules_applied
    assert "```" in result.enhanced


def test_rule_politeness_removal() -> None:
    """Strips politeness phrases."""
    prompt = "Could you please kindly help me build an API?"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "politeness_removal" in result.rules_applied
    assert "kindly" not in result.enhanced.lower()


def test_rule_contradictory_instructions() -> None:
    """Flags contradictory instructions when clarity is low."""
    prompt = "Write a brief but detailed comprehensive summary"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert "contradictions" in result.rules_applied
    assert (
        "contradictory" in result.enhanced.lower()
        or "warning" in result.enhanced.lower()
    )


def test_rules_chain_correctly() -> None:
    """Rules chain — output of one feeds input of next."""
    prompt = "please do something"
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert len(result.rules_applied) >= 2


def test_apply_rules_skips_excluded_rules() -> None:
    """apply_rules with skip_rules omits the listed rules."""
    prompt = "fix bug"
    score = score_prompt(prompt)
    result_skip = apply_rules(prompt, score, skip_rules={"role_assignment"})
    assert "role_assignment" not in result_skip.rules_applied


def test_apply_rules_empty_skip_rules() -> None:
    """apply_rules with empty skip_rules matches default behaviour."""
    prompt = "fix bug"
    score = score_prompt(prompt)
    result_normal = apply_rules(prompt, score)
    result_empty = apply_rules(prompt, score, skip_rules=set())
    assert result_normal.rules_applied == result_empty.rules_applied


def test_apply_rules_idempotent_on_good_prompt() -> None:
    """Good prompts should not be over-modified by rules."""
    prompt = (
        "You are a senior backend developer. Implement a rate "
        "limiter middleware for the Express.js API. Use a sliding "
        "window algorithm with Redis. Limit: 100 requests per "
        "minute per IP. Return 429 status with Retry-After header "
        "when exceeded."
    )
    score = score_prompt(prompt)
    result = apply_rules(prompt, score)
    assert len(result.rules_applied) <= 3


def test_politeness_removal_preserves_newlines_and_structure() -> None:
    """Removing a politeness phrase must not flatten multi-line structure."""
    score = _low_conciseness_score()
    prompt = (
        "Please implement this:\n\n"
        "- parse the file\n"
        "- validate rows\n\n"
        "```\ndef run():\n    return 1\n```"
    )
    result = rule_politeness_removal(prompt, score)
    assert result.applied is True
    # Newlines, list items and the code block survive the cleanup.
    assert "\n" in result.modified_prompt
    assert "- parse the file" in result.modified_prompt
    assert "```" in result.modified_prompt
    assert "    return 1" in result.modified_prompt
    assert "please" not in result.modified_prompt.lower()
