"""Tier 0 Rule Engine: deterministic text transformations.

Each rule is a pure function that takes a prompt and scorer breakdown,
returning a RuleResult. Rules chain — output of one feeds input of next.
Rules only fire when their relevant dimension is weak.

Based on Bsharat et al. 2023 (26 validated principles).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from promptune.scorer import ScoreResult


@dataclass
class RuleResult:
    """Result of a single rule application."""

    modified_prompt: str
    applied: bool
    description: str


@dataclass
class Tier0Result:
    """Result of applying all Tier 0 rules."""

    enhanced: str
    rules_applied: list[str]
    rules_explained: list[tuple[str, str]]


# --- Intent-to-format mapping ---

_INTENT_FORMAT_MAP: dict[str, str] = {
    "coding": "Respond with code and brief explanation.",
    "writing": "Structure your response with clear sections.",
    "research": (
        "Provide a structured explanation with key points."
    ),
    "general": "Provide a clear, organized response.",
}

# --- Intent-to-role mapping ---

_INTENT_ROLE_MAP: dict[str, str] = {
    "coding": "You are an experienced software developer.",
    "writing": "You are a skilled technical writer.",
    "research": "You are a knowledgeable research analyst.",
    "general": "You are a helpful expert assistant.",
}

# --- Domain-to-constraint mapping ---

_DOMAIN_CONSTRAINT_MAP: dict[str, str] = {
    "coding": (
        "Consider edge cases, error handling, and performance."
    ),
    "writing": "Consider audience, tone, and structure.",
    "research": (
        "Consider accuracy, sources, and completeness."
    ),
    "general": "Consider clarity and completeness.",
}

# --- Politeness phrases to remove ---

_POLITENESS_PHRASES = [
    "could you please",
    "would you kindly",
    "please kindly",
    "if you don't mind",
    "i was wondering if",
    "it would be great if",
    "could you",
    "would you",
    "please",
    "kindly",
]

# --- Vague verb replacements ---

_VAGUE_VERB_SUGGESTIONS: dict[str, str] = {
    "do": "implement",
    "make": "create",
    "get": "retrieve",
    "put": "store",
    "handle": "process",
    "deal with": "resolve",
    "take care of": "manage",
    "work on": "develop",
    "look at": "analyze",
    "check": "validate",
    "help": "assist with",
    "fix": "diagnose and fix",
}


# --- Individual rules (each a pure function) ---


def rule_add_output_format(
    prompt: str, score: ScoreResult
) -> RuleResult:
    """Append format instruction when completeness is low."""
    completeness = score.dimensions["completeness"]
    if completeness.score >= 0.4:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    format_hint = _INTENT_FORMAT_MAP.get(
        score.intent, _INTENT_FORMAT_MAP["general"]
    )
    modified = f"{prompt}\n\n{format_hint}"
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Added output format instruction",
    )


def rule_flag_vague_verbs(
    prompt: str, score: ScoreResult
) -> RuleResult:
    """Replace vague verbs with specific alternatives."""
    actionability = score.dimensions["actionability"]
    if actionability.score >= 0.5:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    modified = prompt
    replaced = False
    for vague, specific in _VAGUE_VERB_SUGGESTIONS.items():
        pattern = re.compile(
            r'\b' + re.escape(vague) + r'\b', re.IGNORECASE
        )
        if pattern.search(modified):
            modified = pattern.sub(specific, modified, count=1)
            replaced = True

    return RuleResult(
        modified_prompt=modified,
        applied=replaced,
        description="Replaced vague verbs with specific alternatives",
    )


def rule_too_short(
    prompt: str, score: ScoreResult
) -> RuleResult:
    """Flag very short prompts when specificity is near zero."""
    specificity = score.dimensions["specificity"]
    if specificity.score >= 0.3:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    modified = (
        f"{prompt}\n\n"
        "[Note: Adding more context and detail "
        "will improve results.]"
    )
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Flagged short prompt — adding context recommended",
    )


def rule_add_constraints(
    prompt: str, score: ScoreResult
) -> RuleResult:
    """Append constraints when completeness is low."""
    completeness = score.dimensions["completeness"]
    if completeness.score >= 0.3:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    constraint = _DOMAIN_CONSTRAINT_MAP.get(
        score.intent, _DOMAIN_CONSTRAINT_MAP["general"]
    )
    modified = f"{prompt}\n\n{constraint}"
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Added domain-appropriate constraints",
    )


def rule_negation_rewrite(
    prompt: str, score: ScoreResult
) -> RuleResult:
    """Rewrite negative directives to positive form."""
    clarity = score.dimensions["clarity"]
    if clarity.score >= 0.6:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    modified = prompt
    replaced = False

    rewrites = [
        (r"don'?t use\b", "avoid using"),
        (r"don'?t forget\b", "remember to"),
        (r"don'?t ignore\b", "pay attention to"),
        (r"never use\b", "avoid"),
        (r"do not use\b", "avoid using"),
        # Spelled-out forms must be handled before the generic "do not"
        # catch-all, otherwise they degrade to "avoid forget"/"avoid ignore".
        (r"do not forget\b", "remember to"),
        (r"do not ignore\b", "pay attention to"),
        (r"do not\b", "avoid"),
    ]

    for pattern, replacement in rewrites:
        new_text = re.sub(
            pattern, replacement, modified, flags=re.IGNORECASE
        )
        if new_text != modified:
            modified = new_text
            replaced = True

    return RuleResult(
        modified_prompt=modified,
        applied=replaced,
        description="Rewrote negative directives to positive",
    )


def rule_add_role(
    prompt: str, score: ScoreResult
) -> RuleResult:
    """Prepend role assignment when context score is low."""
    context = score.dimensions["context"]
    if context.score >= 0.3:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    role = _INTENT_ROLE_MAP.get(
        score.intent, _INTENT_ROLE_MAP["general"]
    )
    modified = f"{role} {prompt}"
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Added role assignment",
    )


def rule_code_delimiters(
    prompt: str, score: ScoreResult
) -> RuleResult:
    """Wrap code-like content in code blocks."""
    structure = score.dimensions["structure"]
    if structure.score >= 0.5:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    if "```" in prompt:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    # Patterns are tightened to avoid matching ordinary prose: "class action",
    # "the function of X", "return the report", "import meaning from this" must
    # NOT be treated as code. Definitions require a delimiter; statements must
    # be line-leading (optionally indented), as real code is.
    code_patterns = [
        r'\bdef\s+\w+\s*\(',
        r'\bclass\s+\w+\s*[(:]',
        r'\bfunction\s+\w+\s*\(',
        r'\bconst\s+\w+\s*=',
        r'\blet\s+\w+\s*=',
        r'\bvar\s+\w+\s*=',
        r'(?:^|\n)\s*return\s+\w',
        r'(?:^|\n)\s*(?:import|from)\s+\w',
    ]

    has_code = any(re.search(p, prompt) for p in code_patterns)
    if not has_code:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    lines = prompt.split('\n')
    modified_lines: list[str] = []
    in_code = False
    code_buffer: list[str] = []

    for line in lines:
        is_code_line = any(
            re.search(p, line) for p in code_patterns
        )
        if is_code_line and not in_code:
            in_code = True
            code_buffer.append(line)
        elif in_code and (
            is_code_line
            or line.startswith((' ', '\t'))
        ):
            code_buffer.append(line)
        else:
            if code_buffer:
                modified_lines.append("```")
                modified_lines.extend(code_buffer)
                modified_lines.append("```")
                code_buffer = []
                in_code = False
            modified_lines.append(line)

    if code_buffer:
        modified_lines.append("```")
        modified_lines.extend(code_buffer)
        modified_lines.append("```")

    modified = '\n'.join(modified_lines)
    return RuleResult(
        modified_prompt=modified,
        applied=True,
        description="Wrapped code-like content in code blocks",
    )


def rule_contradictory_instructions(
    prompt: str, score: ScoreResult
) -> RuleResult:
    """Flag contradictory instructions."""
    contradictions = [
        (r'\bbrief\b', r'\bdetailed\b'),
        (r'\bshort\b', r'\bcomprehensive\b'),
        (r'\bsimple\b', r'\bcomplex\b'),
        (r'\bconcise\b', r'\bthorough\b'),
    ]

    lower = prompt.lower()
    for pattern_a, pattern_b in contradictions:
        if re.search(pattern_a, lower) and re.search(
            pattern_b, lower
        ):
            modified = (
                f"{prompt}\n\n"
                "[Warning: Contradictory instructions detected "
                "— consider clarifying scope.]"
            )
            return RuleResult(
                modified_prompt=modified,
                applied=True,
                description="Flagged contradictory instructions",
            )

    return RuleResult(
        modified_prompt=prompt, applied=False, description=""
    )


def rule_politeness_removal(
    prompt: str, score: ScoreResult
) -> RuleResult:
    """Strip politeness phrases (Bsharat principle #1)."""
    conciseness = score.dimensions["conciseness"]
    if conciseness.score >= 0.6:
        return RuleResult(
            modified_prompt=prompt, applied=False, description=""
        )

    modified = prompt
    replaced = False

    for phrase in _POLITENESS_PHRASES:
        pattern = re.compile(
            r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE
        )
        new_text = pattern.sub("", modified)
        if new_text != modified:
            modified = new_text
            replaced = True

    # Clean up whitespace and orphaned punctuation left by removals.
    # Collapse only *internal* horizontal runs (those following a non-space
    # char), so multi-line structure AND line-leading indentation (code
    # blocks, lists, blank-line-separated sections) survive a removal.
    modified = re.sub(r'(?<=\S)[ \t]+', ' ', modified)
    modified = re.sub(r'[ \t]+\n', '\n', modified)
    modified = re.sub(r'\n{3,}', '\n\n', modified)
    modified = re.sub(r'[ \t]+([,;.!?])', r'\1', modified)
    modified = re.sub(r'([,;])(?:[ \t]*[,;])+', r'\1', modified)
    modified = re.sub(r'[,;]+([ \t]*[.!?])', r'\1', modified)
    modified = re.sub(r'^[ \t,;.!?]+', '', modified)
    modified = re.sub(r'[,;][ \t]*$', '', modified)
    modified = modified.strip()

    return RuleResult(
        modified_prompt=modified,
        applied=replaced,
        description="Removed politeness phrases",
    )


# --- Rule pipeline ---

RuleFn = Callable[[str, ScoreResult], RuleResult]

_RULE_PIPELINE: list[tuple[str, RuleFn]] = [
    ("politeness_removal", rule_politeness_removal),
    ("negation_rewrite", rule_negation_rewrite),
    ("vague_verbs", rule_flag_vague_verbs),
    ("role_assignment", rule_add_role),
    ("output_format", rule_add_output_format),
    ("constraints", rule_add_constraints),
    ("code_delimiters", rule_code_delimiters),
    ("contradictions", rule_contradictory_instructions),
    ("too_short", rule_too_short),
]


def apply_rules(
    prompt: str,
    score: ScoreResult,
    skip_rules: set[str] | None = None,
) -> Tier0Result:
    """Apply all Tier 0 rules in order. Rules chain.

    Args:
        skip_rules: Set of rule names to skip (from preference learning).
    """
    current = prompt
    applied: list[str] = []
    explained: list[tuple[str, str]] = []
    excluded = skip_rules or set()

    for name, rule_fn in _RULE_PIPELINE:
        if name in excluded:
            continue
        result = rule_fn(current, score)
        if result.applied:
            current = result.modified_prompt
            applied.append(name)
            explained.append((name, result.description))

    return Tier0Result(
        enhanced=current,
        rules_applied=applied,
        rules_explained=explained,
    )
