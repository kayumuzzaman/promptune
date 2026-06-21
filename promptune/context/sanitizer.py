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
    # JSON Web Tokens (header.payload.signature). The base64url header is
    # low-entropy and can slip past the entropy heuristic, so match the
    # structure explicitly.
    re.compile(
        r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    ),
    # Any URL carrying basic-auth userinfo (scheme://user:pass@): covers
    # postgres, postgresql, mysql, mongodb, redis, amqp(s), mssql, http(s),
    # ftp, etc. — redacts the credential-bearing prefix. The userinfo classes
    # exclude only '/' and whitespace (not ':'/'@'), so they stay within the
    # authority component yet span passwords that themselves contain '@',
    # redacting the whole credential rather than leaking a fragment.
    re.compile(
        r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^/\s]*:[^/\s]*@",
        re.IGNORECASE,
    ),
    # PEM private-key blocks (markers + body, any body length).
    re.compile(
        r"-----BEGIN[^-]*PRIVATE KEY-----.*?-----END[^-]*-----",
        re.DOTALL,
    ),
]

_KEYWORD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        # Value bound to non-whitespace, not the rest of the line: rank_context
        # sanitizes a single ` | `-joined context line, so a greedy `[^\n]+`
        # let one `token=` substring redact every later signal. Real secret
        # values are token-shaped (no spaces); any space-separated remainder
        # that is itself a secret is still caught by the high-entropy pass.
        r"(?P<key>password|passwd|secret|token|api_key|apikey)"
        r"(?P<sep>\s*[=:]\s*)\S+",
        re.IGNORECASE,
    ),
]

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9+/_-]{20,}={0,2}")

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


def _looks_like_secret(token: str) -> bool:
    """Heuristic: long token that resembles a key, hash, or token value."""
    if len(token) < 20:
        return False
    if re.fullmatch(r"[0-9a-fA-F]+", token) and len(token) >= 32:
        return True
    has_lower = any(c.islower() for c in token)
    has_upper = any(c.isupper() for c in token)
    has_digit = any(c.isdigit() for c in token)
    classes = has_lower + has_upper + has_digit
    entropy = _shannon_entropy(token)
    if "/" in token:
        # Structured path/branch/ticket names (e.g. "feature/JIRA-1234-x")
        # split into many short segments on '/', '-' and '_'. A real
        # slash-bearing base64 secret instead has a long unbroken
        # high-entropy run. Treat tokens whose longest separator-delimited
        # segment is short as structured context, not secrets.
        longest_segment = max(
            (len(seg) for seg in re.split(r"[/_-]", token)), default=0
        )
        if longest_segment < 16:
            return False
        # Path-like vs base64-with-slash: a source path is typically
        # digit-free and lower entropy, while a slash-bearing credential has
        # digits and high entropy. Require the stronger signal so paths such
        # as "packages/src/CheckoutExperienceManager" aren't redacted while
        # base64 secrets containing "/" still are.
        return has_digit and classes >= 2 and entropy >= 4.0
    if has_digit and (has_lower or has_upper) and entropy >= 3.5:
        return True
    return entropy >= 4.0 and classes >= 2


def _redact_high_entropy(text: str) -> str:
    """Redact high-entropy strings that look like secrets, anywhere in text."""

    def _check_and_redact(match: re.Match[str]) -> str:
        value = match.group(0)
        return _REDACTED if _looks_like_secret(value) else value

    return _TOKEN_PATTERN.sub(_check_and_redact, text)


def sanitize(text: str) -> str:
    """Remove all secrets from text."""
    result = text

    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(_REDACTED, result)

    for pattern in _KEYWORD_PATTERNS:
        result = pattern.sub(
            lambda m: m.group("key") + m.group("sep") + _REDACTED,
            result,
        )

    result = _redact_high_entropy(result)

    return result
