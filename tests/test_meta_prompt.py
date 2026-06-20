"""Step 6: Meta-Prompt Engine — tests."""

from promptune.meta_prompt import (
    build_system_prompt,
    detect_domain,
    detect_intent,
    detect_stack,
)


def test_detect_intent_coding() -> None:
    """'build a REST API' -> coding intent."""
    assert detect_intent("build a REST API with Flask") == "coding"


def test_detect_intent_writing() -> None:
    """'write a blog post' -> writing intent."""
    assert detect_intent("write a blog post about AI") == "writing"


def test_detect_intent_research() -> None:
    """'explain how DNS works' -> research intent."""
    assert detect_intent("explain how DNS works") == "research"


def test_detect_domain_webdev() -> None:
    """'React component' -> web dev domain."""
    assert detect_domain("create a React component for login") == "webdev"


def test_detect_domain_datascience() -> None:
    """'train a model' -> data science domain."""
    assert detect_domain("train a model on this dataset") == "datascience"


def test_detect_stack_python() -> None:
    """'using Flask' -> Python stack detected."""
    stack = detect_stack("build an API using Flask and SQLAlchemy")
    assert "python" in stack
    assert "flask" in stack


def test_detect_stack_ignores_english_go() -> None:
    """The English verb 'go' must not trigger Go-stack detection."""
    assert "go" not in detect_stack("go fast and build something")
    assert "go" in detect_stack("update the go.mod and add a goroutine")


def test_detect_stack_ignores_english_inflections() -> None:
    """Short, collision-prone stack keywords must not match common English.

    `nest`/`node`/`pip`/`express` are roots of everyday words; with no count
    threshold a single inflected match (e.g. "nested" -> typescript) injects a
    wrong tech stack into the LLM system prompt and template domain aliases.
    """
    assert "typescript" not in detect_stack("fix the nested loop in Python")
    assert "javascript" not in detect_stack("traverse all the graph nodes")
    assert "python" not in detect_stack("connect the unix pipes between stages")
    assert "javascript" not in detect_stack("clearly expressed the requirements")
    assert "react" not in detect_stack("the page reacted slowly to the click")


def test_detect_stack_still_matches_exact_short_keywords() -> None:
    """Exact-word forms of the collision-prone keywords still detect the stack."""
    assert "python" in detect_stack("install it with pip")
    assert "javascript" in detect_stack("run it under node")
    assert "typescript" in detect_stack("build it with nest")
    assert "javascript" in detect_stack("use express for the server")
    assert "react" in detect_stack("build the UI in react")


def test_detect_intent_word_boundary() -> None:
    """Intent keywords match whole words, not substrings."""
    from promptune.meta_prompt import detect_intent

    # "api" must not match inside "rapidly"
    assert detect_intent("rapidly iterate on the team plan") != "coding"


def test_detect_intent_matches_regular_plurals() -> None:
    """Plural coding keywords still count (e.g. 'tests' -> 'test')."""
    from promptune.meta_prompt import detect_intent

    assert detect_intent("write tests") == "coding"
    assert detect_intent("add api endpoints") == "coding"


def test_detect_intent_matches_verb_inflections() -> None:
    """-ing/-ed/-es inflections count, incl. consonant doubling."""
    from promptune.meta_prompt import detect_intent

    assert detect_intent("debugging the parser") == "coding"
    assert detect_intent("refactoring the module") == "coding"
    assert detect_intent("write classes for the model") == "coding"


def test_keyword_match_stays_anchored() -> None:
    """Inflection support must not reintroduce substring false positives."""
    from promptune.meta_prompt import _keyword_matches

    assert _keyword_matches("write tests", "test")
    assert _keyword_matches("debugging now", "debug")
    # "api" must not match inside "rapidly"; "app" not inside "approach".
    assert not _keyword_matches("rapidly iterate", "api")
    assert not _keyword_matches("a new approach", "app")
    assert detect_intent("build a REST api endpoint") == "coding"


def test_detect_domain_word_boundary() -> None:
    """Domain keywords match whole words, not substrings."""
    from promptune.meta_prompt import detect_domain

    # "data" must not match inside "update"
    assert detect_domain("update the readme file") != "datascience"


def test_build_system_prompt_minimal() -> None:
    """Minimal style produces conservative prompt."""
    prompt = build_system_prompt(
        intent="coding",
        domain="webdev",
        stack=["python", "flask"],
        style="minimal",
    )
    assert "clarity" in prompt.lower() or "grammar" in prompt.lower()
    assert "preserve" in prompt.lower()


def test_build_system_prompt_balanced() -> None:
    """Balanced style adds structure."""
    prompt = build_system_prompt(
        intent="coding",
        domain="webdev",
        stack=["python", "flask"],
        style="balanced",
    )
    assert "structure" in prompt.lower()


def test_build_system_prompt_detailed() -> None:
    """Detailed style adds edge cases."""
    prompt = build_system_prompt(
        intent="coding",
        domain="webdev",
        stack=["python", "flask"],
        style="detailed",
    )
    assert "edge case" in prompt.lower() or "criteria" in prompt.lower()


def test_system_prompt_includes_context() -> None:
    """Detected intent/domain/stack in output."""
    prompt = build_system_prompt(
        intent="coding",
        domain="webdev",
        stack=["typescript", "react"],
        style="balanced",
    )
    assert "coding" in prompt.lower()
    assert "webdev" in prompt.lower() or "web" in prompt.lower()


def test_preserves_user_intent() -> None:
    """Enhanced prompt instructions don't contradict original."""
    prompt = build_system_prompt(
        intent="writing",
        domain="general",
        stack=[],
        style="balanced",
    )
    assert "preserve" in prompt.lower() or "intent" in prompt.lower()
