"""Task 8: Provider-Specific Formatting — tests."""

from __future__ import annotations

from promptune.formatter import (
    FormatStyle,
    detect_format_style,
    format_prompt,
)

# --- FormatStyle enum ---


def test_format_style_values() -> None:
    """FormatStyle has xml, markdown, plain values."""
    assert FormatStyle.XML.value == "xml"
    assert FormatStyle.MARKDOWN.value == "markdown"
    assert FormatStyle.PLAIN.value == "plain"


# --- Auto-detection ---


def test_detect_claude_xml() -> None:
    """Claude models get XML format."""
    assert (
        detect_format_style("claude-sonnet-4-20250514")
        == FormatStyle.XML
    )


def test_detect_o3_reasoning_markdown() -> None:
    """o3 reasoning models match the markdown rule."""
    assert detect_format_style("o3-mini") == FormatStyle.MARKDOWN
    assert detect_format_style("o3") == FormatStyle.MARKDOWN


def test_extract_param_count_handles_decimals() -> None:
    """Decimal model sizes are parsed as a whole, not just the fraction."""
    from promptune.formatter import _extract_param_count

    assert _extract_param_count("qwen3-0.6b") == 0
    assert _extract_param_count("qwen2.5-1.5b") == 1
    assert _extract_param_count("llama-70b") == 70
    assert _extract_param_count("gpt-4o-mini") is None


def test_detect_gemini_xml() -> None:
    """Gemini models get XML format."""
    assert (
        detect_format_style("gemini-1.5-pro")
        == FormatStyle.XML
    )


def test_detect_gpt_markdown() -> None:
    """GPT models get Markdown format."""
    assert (
        detect_format_style("gpt-4o") == FormatStyle.MARKDOWN
    )


def test_detect_o1_markdown() -> None:
    """o1 reasoning models get Markdown format."""
    assert (
        detect_format_style("o1-preview")
        == FormatStyle.MARKDOWN
    )


def test_detect_deepseek_r1_plain() -> None:
    """DeepSeek R1 reasoning model gets Plain format."""
    assert (
        detect_format_style("deepseek-r1")
        == FormatStyle.PLAIN
    )
    assert (
        detect_format_style("deepseek-reasoner")
        == FormatStyle.PLAIN
    )


def test_detect_phi_plain() -> None:
    """Phi models get Plain format."""
    assert (
        detect_format_style("phi-3") == FormatStyle.PLAIN
    )


def test_detect_gemma_plain() -> None:
    """Gemma models get Plain format."""
    assert (
        detect_format_style("gemma-2") == FormatStyle.PLAIN
    )


def test_detect_mistral_large_markdown() -> None:
    """Mistral large models get Markdown format."""
    assert (
        detect_format_style("mistral-large-latest")
        == FormatStyle.MARKDOWN
    )


def test_detect_deepseek_chat_markdown() -> None:
    """DeepSeek chat models get Markdown format."""
    assert (
        detect_format_style("deepseek-chat")
        == FormatStyle.MARKDOWN
    )


def test_detect_grok_markdown() -> None:
    """Grok models get Markdown format."""
    assert (
        detect_format_style("grok-2") == FormatStyle.MARKDOWN
    )


def test_detect_command_r_markdown() -> None:
    """Command R models get Markdown format."""
    assert (
        detect_format_style("command-r-plus")
        == FormatStyle.MARKDOWN
    )


def test_detect_openrouter_prefix_stripped() -> None:
    """OpenRouter prefix is stripped before matching."""
    assert (
        detect_format_style(
            "anthropic/claude-sonnet-4-20250514"
        )
        == FormatStyle.XML
    )
    assert (
        detect_format_style("openai/gpt-4o")
        == FormatStyle.MARKDOWN
    )


def test_detect_small_model_plain() -> None:
    """Models <7B params get Plain format."""
    assert (
        detect_format_style("llama-3b") == FormatStyle.PLAIN
    )
    assert (
        detect_format_style("qwen-2.5-3b")
        == FormatStyle.PLAIN
    )


def test_detect_large_model_markdown() -> None:
    """Models >=7B params get Markdown format."""
    assert (
        detect_format_style("llama-70b")
        == FormatStyle.MARKDOWN
    )


def test_detect_unknown_model_markdown() -> None:
    """Unknown model defaults to Markdown."""
    assert (
        detect_format_style("some-unknown-model-v2")
        == FormatStyle.MARKDOWN
    )


def test_detect_ministral_plain() -> None:
    """Small Mistral variants get Plain format."""
    assert (
        detect_format_style("ministral-8b")
        == FormatStyle.PLAIN
    )
    assert (
        detect_format_style("mistral-small-latest")
        == FormatStyle.PLAIN
    )


# --- Format output ---


def test_format_xml_wraps_sections() -> None:
    """XML format wraps content in XML tags."""
    result = format_prompt(
        "You are a Python expert.",
        "Build a REST API with Flask.",
        "- Use SQLAlchemy\n- Add JWT auth",
        FormatStyle.XML,
    )
    assert "<instructions>" in result
    assert "<task>" in result
    assert "</instructions>" in result


def test_format_markdown_uses_headers() -> None:
    """Markdown format uses ## headers."""
    result = format_prompt(
        "You are a Python expert.",
        "Build a REST API with Flask.",
        "- Use SQLAlchemy\n- Add JWT auth",
        FormatStyle.MARKDOWN,
    )
    assert "## " in result


def test_format_plain_uses_labels() -> None:
    """Plain format uses label: value structure."""
    result = format_prompt(
        "You are a Python expert.",
        "Build a REST API with Flask.",
        "- Use SQLAlchemy\n- Add JWT auth",
        FormatStyle.PLAIN,
    )
    assert "Role:" in result or "Task:" in result


def test_format_empty_sections_omitted() -> None:
    """Empty sections are not included in output."""
    result = format_prompt(
        "", "Build something.", "", FormatStyle.XML
    )
    assert "<instructions>" not in result
    assert "<requirements>" not in result
    assert "<task>" in result
    assert "Build something" in result
