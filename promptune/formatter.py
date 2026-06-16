"""Provider-specific prompt formatting with auto-detection."""

from __future__ import annotations

import re
from enum import Enum


class FormatStyle(Enum):
    """Prompt format styles for different LLM families."""

    XML = "xml"
    MARKDOWN = "markdown"
    PLAIN = "plain"


# Ordered list — first match wins.
MODEL_FORMAT_MAP: list[tuple[str, FormatStyle]] = [
    # Plain preference (specific patterns first)
    (r"deepseek[-_/]?(reasoner|r1)", FormatStyle.PLAIN),
    (r"phi[-_]?\d", FormatStyle.PLAIN),
    (r"gemma[-_]?\d", FormatStyle.PLAIN),
    # XML preference
    (r"claude", FormatStyle.XML),
    (r"gemini", FormatStyle.XML),
    # Markdown preference
    (r"gpt[-_]?\d", FormatStyle.MARKDOWN),
    (r"o[1-4][-_]?(mini|preview)?", FormatStyle.MARKDOWN),
    (
        r"mistral[-_]?(large|medium)|mixtral|magistral",
        FormatStyle.MARKDOWN,
    ),
    (r"codestral|devstral", FormatStyle.MARKDOWN),
    (
        r"deepseek[-_/]?(chat|v[23]|coder)",
        FormatStyle.MARKDOWN,
    ),
    (r"grok", FormatStyle.MARKDOWN),
    (r"command[-_]?r", FormatStyle.MARKDOWN),
    (r"jamba", FormatStyle.MARKDOWN),
    (r"dbrx", FormatStyle.MARKDOWN),
]

# Size-aware families
SIZE_AWARE_FAMILIES: list[tuple[str, dict]] = [
    (
        r"llama",
        {
            "threshold": 7,
            "above": FormatStyle.MARKDOWN,
            "below": FormatStyle.PLAIN,
        },
    ),
    (
        r"qwen",
        {
            "threshold": 7,
            "above": FormatStyle.MARKDOWN,
            "below": FormatStyle.PLAIN,
        },
    ),
    (
        r"mistral[-_]?(small|tiny)|ministral",
        {"force": FormatStyle.PLAIN},
    ),
]


def _strip_provider_prefix(model_id: str) -> str:
    """Strip OpenRouter/Together AI provider prefixes."""
    if "/" in model_id:
        return model_id.split("/")[-1]
    return model_id


def _extract_param_count(model_id: str) -> int | None:
    """Extract parameter count in billions (floored to a whole number)."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*[bB]\b", model_id)
    if match:
        return int(float(match.group(1)))
    return None


def detect_format_style(model_id: str) -> FormatStyle:
    """Auto-detect format style from model ID."""
    stripped = _strip_provider_prefix(model_id).lower()

    for pattern, style in MODEL_FORMAT_MAP:
        if re.search(pattern, stripped):
            return style

    param_count = _extract_param_count(stripped)
    for pattern, config in SIZE_AWARE_FAMILIES:
        if re.search(pattern, stripped):
            if "force" in config:
                return FormatStyle(config["force"])
            if param_count is not None:
                threshold: int = config["threshold"]
                if param_count >= threshold:
                    return FormatStyle(config["above"])
                return FormatStyle(config["below"])
            above = config.get(
                "above", FormatStyle.MARKDOWN
            )
            return FormatStyle(above)

    return FormatStyle.MARKDOWN


def format_prompt(
    role: str,
    task: str,
    requirements: str,
    style: FormatStyle,
) -> str:
    """Format prompt sections into the target style."""
    if style == FormatStyle.XML:
        return _format_xml(role, task, requirements)
    if style == FormatStyle.MARKDOWN:
        return _format_markdown(role, task, requirements)
    return _format_plain(role, task, requirements)


def _format_xml(
    role: str, task: str, requirements: str
) -> str:
    """Format as XML tags."""
    parts: list[str] = []
    if role:
        parts.append(
            f"<instructions>{role}</instructions>"
        )
    if task:
        parts.append(f"<task>{task}</task>")
    if requirements:
        parts.append(
            f"<requirements>{requirements}</requirements>"
        )
    return "\n\n".join(parts)


def _format_markdown(
    role: str, task: str, requirements: str
) -> str:
    """Format with Markdown headers."""
    parts: list[str] = []
    if role:
        parts.append(f"## Role\n{role}")
    if task:
        parts.append(f"## Task\n{task}")
    if requirements:
        parts.append(f"## Requirements\n{requirements}")
    return "\n\n".join(parts)


def _format_plain(
    role: str, task: str, requirements: str
) -> str:
    """Format with plain label: value structure."""
    parts: list[str] = []
    if role:
        parts.append(f"Role: {role}")
    if task:
        parts.append(f"Task: {task}")
    if requirements:
        parts.append(f"Requirements: {requirements}")
    return "\n\n".join(parts)
