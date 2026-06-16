"""Meta-prompt engine: intent/domain/stack detection and system prompt builder."""

from __future__ import annotations

import re

# Keyword maps for detection
_INTENT_KEYWORDS: dict[str, list[str]] = {
    "coding": [
        "build", "create", "implement", "code", "develop", "api",
        "function", "class", "app", "application", "script", "program",
        "debug", "fix", "refactor", "deploy", "test", "endpoint",
        "database", "server", "cli", "tool", "library", "package",
        "component", "module", "service", "migrate",
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

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "webdev": [
        "react", "vue", "angular", "html", "css", "javascript",
        "typescript", "frontend", "backend", "fullstack", "web",
        "api", "rest", "graphql", "nextjs", "svelte", "dom",
        "browser", "http", "url", "webpack", "tailwind",
    ],
    "datascience": [
        "data", "model", "train", "dataset", "pandas", "numpy",
        "scikit", "tensorflow", "pytorch", "ml", "machine learning",
        "neural", "prediction", "regression", "classification",
        "jupyter", "notebook", "visualization", "plot",
    ],
    "devops": [
        "docker", "kubernetes", "ci/cd", "pipeline", "deploy",
        "terraform", "aws", "gcp", "azure", "infrastructure",
        "monitoring", "nginx", "ansible", "helm", "container",
    ],
}

_STACK_KEYWORDS: dict[str, list[str]] = {
    "python": [
        "python", "flask", "django", "fastapi", "sqlalchemy",
        "pytest", "pip", "poetry", "pandas", "numpy",
    ],
    "javascript": [
        "javascript", "node", "npm", "yarn", "express", "deno",
    ],
    "typescript": [
        "typescript", "ts", "tsx", "nextjs", "nest",
    ],
    "react": ["react", "jsx", "tsx", "nextjs"],
    "flask": ["flask"],
    "django": ["django"],
    "go": ["golang", "goroutine", "go.mod"],
    "rust": ["rust", "cargo"],
}


def _keyword_matches(text: str, kw: str) -> bool:
    """Whole-word keyword match that also accepts regular English inflections.

    Anchored at a word boundary (so "api" never matches inside "rapidly"), it
    additionally accepts plurals and verb forms — ``-s``/``-es``/``-ed``/
    ``-ing`` — including single-consonant doubling like ``debug`` -> ``debugging``
    and ``program`` -> ``programming``. It does not cover spelling-changing
    forms such as ``create`` -> ``creating``.
    """
    if not kw:
        return False
    last = re.escape(kw[-1])
    pattern = rf"\b{re.escape(kw)}(?:{last}?(?:ing|ed)|e?s)?\b"
    return re.search(pattern, text) is not None


def detect_intent(prompt: str) -> str:
    """Detect the intent of a prompt: coding, writing, or research."""
    lower = prompt.lower()
    scores: dict[str, int] = {intent: 0 for intent in _INTENT_KEYWORDS}
    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if _keyword_matches(lower, kw):
                scores[intent] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


def detect_domain(prompt: str) -> str:
    """Detect the domain: webdev, datascience, devops, or general."""
    lower = prompt.lower()
    scores: dict[str, int] = {domain: 0 for domain in _DOMAIN_KEYWORDS}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if _keyword_matches(lower, kw):
                scores[domain] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


def detect_stack(prompt: str) -> list[str]:
    """Detect technology stack mentioned in the prompt."""
    lower = prompt.lower()
    found: list[str] = []
    for tech, keywords in _STACK_KEYWORDS.items():
        for kw in keywords:
            if _keyword_matches(lower, kw):
                if tech not in found:
                    found.append(tech)
                break
    return found


def build_system_prompt(
    intent: str,
    domain: str,
    stack: list[str],
    style: str,
) -> str:
    """Build a system prompt for the AI provider."""
    parts: list[str] = [
        "You are a prompt enhancer. Your job is to take a user's "
        "rough prompt and return an improved, clearer version.",
        "",
        f"Detected context: intent={intent}, domain={domain}.",
    ]

    if stack:
        parts.append(f"Technology stack: {', '.join(stack)}.")

    parts.append("")

    if style == "minimal":
        parts.append(
            "Style: Minimal. Fix grammar, improve clarity, and "
            "preserve the original scope exactly. Do not add new "
            "requirements or expand the scope."
        )
    elif style == "balanced":
        parts.append(
            "Style: Balanced. Add structure, suggest constraints, "
            "remove ambiguity, and stay lean. Preserve the user's "
            "core intent while making the prompt more actionable."
        )
    elif style == "detailed":
        parts.append(
            "Style: Thorough. Expand the prompt with edge cases, "
            "acceptance criteria, and technical suggestions. "
            "Be comprehensive but stay relevant to the original ask."
        )

    parts.append("")
    parts.append(
        "Rules: Preserve the user's core intent. Do not hallucinate "
        "requirements. Output only the enhanced prompt text, nothing "
        "else."
    )

    return "\n".join(parts)
