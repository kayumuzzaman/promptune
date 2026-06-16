"""Task 6: Context Fingerprinting — secret sanitizer tests."""

from __future__ import annotations

from promptune.context.sanitizer import sanitize


def test_sanitize_api_key_sk_prefix() -> None:
    """Redacts strings starting with sk-."""
    text = "api_key=sk-ant-abc123xyz456"
    result = sanitize(text)
    assert "sk-ant-abc123xyz456" not in result
    assert "[REDACTED]" in result


def test_sanitize_github_token() -> None:
    """Redacts GitHub personal access tokens."""
    text = "token: ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
    result = sanitize(text)
    assert "ghp_" not in result
    assert "[REDACTED]" in result


def test_sanitize_aws_key() -> None:
    """Redacts AWS access key IDs."""
    text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
    result = sanitize(text)
    assert "AKIA" not in result


def test_sanitize_bearer_token() -> None:
    """Redacts Bearer tokens."""
    text = (
        "Authorization: Bearer "
        "eyJhbGciOiJIUzI1NiJ9.eyJ0ZXN0IjoidGVzdCJ9.abc123"
    )
    result = sanitize(text)
    assert "eyJhbGci" not in result


def test_sanitize_db_connection_string() -> None:
    """Redacts database connection strings with passwords."""
    text = (
        "DATABASE_URL="
        "postgres://user:s3cretP@ss@localhost:5432/mydb"
    )
    result = sanitize(text)
    assert "s3cretP@ss" not in result


def test_sanitize_password_keyword() -> None:
    """Redacts values near password= keywords."""
    text = "password=my_super_secret_123"
    result = sanitize(text)
    assert "my_super_secret_123" not in result


def test_sanitize_high_entropy_string() -> None:
    """Redacts high-entropy base64-like strings."""
    text = (
        "secret: "
        "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5"
    )
    result = sanitize(text)
    assert (
        "[REDACTED]" in result
        or "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5"
        not in result
    )


def test_sanitize_preserves_normal_text() -> None:
    """Normal text without secrets passes through."""
    text = (
        "branch=fix/auth-redirect | stack=typescript,nextjs"
    )
    result = sanitize(text)
    assert result == text


def test_sanitize_slack_token() -> None:
    """Redacts Slack tokens."""
    text = "SLACK_TOKEN=xoxb-1234567890-abcdefghij"
    result = sanitize(text)
    assert "xoxb-" not in result


def test_sanitize_multiple_secrets() -> None:
    """Redacts multiple secrets in one string."""
    text = "key1=sk-abc123 key2=ghp_def456"
    result = sanitize(text)
    assert "sk-abc123" not in result
    assert "ghp_def456" not in result


def test_sanitize_keyword_value_with_equals_does_not_leak() -> None:
    """A keyword value containing '=' is fully redacted (no fragment leak)."""
    text = "api_key: foo=bar"
    result = sanitize(text)
    assert "foo" not in result
    assert "bar" not in result
    assert "[REDACTED]" in result


def test_sanitize_bare_hex_secret() -> None:
    """Redacts a long bare hex secret with no preceding keyword."""
    text = "value bd1e4d8cf4430b9c8e1f2a3d4e5f60718293a4b5"
    result = sanitize(text)
    assert "bd1e4d8cf4430b9c8e1f2a3d4e5f60718293a4b5" not in result
    assert "[REDACTED]" in result


def test_sanitize_secret_at_start_of_segment() -> None:
    """Redacts a high-entropy token even at the start of the string."""
    text = "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5"
    result = sanitize(text)
    assert text not in result
    assert "[REDACTED]" in result


def test_sanitize_preserves_camelcase_source_paths() -> None:
    """A normal source path with a long CamelCase filename isn't redacted."""
    text = (
        "modified_files=packages/frontend/src/"
        "CheckoutExperienceManager.tsx"
    )
    result = sanitize(text)
    assert "CheckoutExperienceManager.tsx" in result
    assert "[REDACTED]" not in result


def test_sanitize_still_redacts_secret_next_to_a_path() -> None:
    """A secret beside a path is still redacted."""
    text = "see config/app.py token sk-ant-abc123xyz456def"
    result = sanitize(text)
    assert "sk-ant-abc123xyz456def" not in result
    assert "[REDACTED]" in result


def test_sanitize_redacts_slash_bearing_base64_secret() -> None:
    """A high-entropy base64 token containing '/' is still redacted."""
    secret = "AbCdEfGhIjKlMnOp/QrStUvWxYz012345/AbCdEfGhIjKl"
    result = sanitize(f"creds={secret}")
    assert secret not in result
    assert "[REDACTED]" in result
