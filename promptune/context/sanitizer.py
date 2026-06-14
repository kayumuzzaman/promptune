"""Secret sanitizer — redacts sensitive values."""

from __future__ import annotations

import math
import re
from collections import Counter

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bsk-[a-zA-Z0-9_-]{6,}\b"),
    re.compile(r"\bghp_[a-zA-Z0-9]{6,}\b"),
    re.compile(r"\bghs_[a-zA-Z0-9]{6,}\b"),
    re.compile(r"\bgho_[a-zA-Z0-9]{6,}\b"),
    re.compile(r"\bghu_[a-zA-Z0-9]{6,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bxoxb-[a-zA-Z0-9-]+\b"),
    re.compile(r"\bxoxp-[a-zA-Z0-9-]+\b"),
    re.compile(
        r"Bearer\s+[a-zA-Z0-9._-]{20,}",
        re.IGNORECASE,
    ),
    re.compile(
        r"(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@",
        re.IGNORECASE,
    ),
]

_KEYWORD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(password|passwd|secret|token|api_key|apikey)"
        r"\s*[=:]\s*\S+",
        re.IGNORECASE,
    ),
]

_REDACTED = "[REDACTED]"


def _shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    counter = Counter(s)
    length = len(s)
    entropy = 0.0
    for count in counter.values():
        p = count / length
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def _redact_high_entropy(text: str) -> str:
    """Redact high-entropy strings that look like secrets."""
    pattern = re.compile(r"(?<=[=:\s])[a-zA-Z0-9+/=_-]{20,}")

    def _check_and_redact(match: re.Match[str]) -> str:
        value = match.group(0)
        entropy = _shannon_entropy(value)
        if entropy > 4.5:
            return _REDACTED
        return value

    return pattern.sub(_check_and_redact, text)


def sanitize(text: str) -> str:
    """Remove all secrets from text."""
    result = text

    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(_REDACTED, result)

    for pattern in _KEYWORD_PATTERNS:
        result = pattern.sub(
            lambda m: (
                m.group(0).split("=")[0] + "=" + _REDACTED
                if "=" in m.group(0)
                else m.group(0).split(":")[0]
                + ": "
                + _REDACTED
            ),
            result,
        )

    result = _redact_high_entropy(result)

    return result
