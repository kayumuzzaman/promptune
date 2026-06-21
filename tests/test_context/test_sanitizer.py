"""Task 6: Context Fingerprinting — secret sanitizer tests."""

from __future__ import annotations

from promptune.context.sanitizer import sanitize


def test_sanitize_api_key_sk_prefix() -> None:
    """Redacts strings starting with sk-."""
    text = "api_key=sk-ant-abc123xyz456"
    result = sanitize(text)
    assert "sk-ant-abc123xyz456" not in result
    assert "[REDACTED]" in result


def test_sanitize_keyword_value_does_not_swallow_following_signals() -> None:
    """A bounded keyword value must not redact later signals on a joined line.

    rank_context sanitizes the single ` | `-joined context line, so a greedy
    value match after one `token=`/`api_key=` substring used to wipe every
    later signal (errors, frameworks, ...). The value is bounded to non-space.
    """
    text = "token=abc | error: real failure here | frameworks: react"
    result = sanitize(text)
    assert "token=[REDACTED]" in result
    assert "error: real failure here" in result
    assert "frameworks: react" in result


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


def test_sanitize_keyword_value_with_pipe_does_not_leak() -> None:
    """A keyword value containing '|' is fully redacted (no suffix leak)."""
    text = "password=abc|def"
    result = sanitize(text)
    assert "def" not in result
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


def test_sanitize_postgresql_connection_string() -> None:
    """Redacts canonical 'postgresql://' scheme (not just 'postgres')."""
    text = "DATABASE_URL=postgresql://admin:Pr0dP4ss@db:5432/app"
    result = sanitize(text)
    assert "Pr0dP4ss" not in result
    assert "[REDACTED]" in result


def test_sanitize_amqps_connection_string() -> None:
    """Redacts AMQP(S) broker credentials."""
    text = "BROKER=amqps://user:Secr3tBrok3r@broker.example.com"
    result = sanitize(text)
    assert "Secr3tBrok3r" not in result


def test_sanitize_mssql_connection_string() -> None:
    """Redacts MSSQL connection credentials."""
    text = "DSN=mssql://sa:Passw0rdSql@sqlsrv:1433/db"
    result = sanitize(text)
    assert "Passw0rdSql" not in result


def test_sanitize_http_basic_auth_userinfo() -> None:
    """Redacts basic-auth userinfo passwords in http(s) URLs."""
    text = "curl https://deploy:hunter2pass@example.com/api"
    result = sanitize(text)
    assert "hunter2pass" not in result


def test_sanitize_redis_connection_string_still_works() -> None:
    """Existing redis scheme still redacted after broadening."""
    text = "CACHE=redis://user:r3disSecret@cache:6379/0"
    result = sanitize(text)
    assert "r3disSecret" not in result


def test_sanitize_mongodb_connection_string_still_works() -> None:
    """Existing mongodb scheme still redacted after broadening."""
    text = "MONGO=mongodb://user:m0ngoSecret@mongo:27017/db"
    result = sanitize(text)
    assert "m0ngoSecret" not in result


def test_sanitize_preserves_jira_ticketed_branch_name() -> None:
    """A ticketed branch name is context, not a secret — must survive."""
    text = "branch=feature/JIRA-1234-add-login-flow"
    result = sanitize(text)
    assert "feature/JIRA-1234-add-login-flow" in result
    assert "[REDACTED]" not in result


def test_sanitize_preserves_versioned_release_branch_name() -> None:
    """A versioned release branch name must survive un-redacted."""
    text = "branch=release/v2.3.1-hotfix-aaa"
    result = sanitize(text)
    assert "release/v2.3.1-hotfix-aaa" in result
    assert "[REDACTED]" not in result


def test_sanitize_still_redacts_aws_key_after_branch_relaxation() -> None:
    """AWS key still redacted despite branch-name relaxation."""
    text = "key=AKIAIOSFODNN7EXAMPLE branch=feature/JIRA-1234-x"
    result = sanitize(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in result
    assert "feature/JIRA-1234-x" in result


def test_sanitize_still_redacts_jwt_after_branch_relaxation() -> None:
    """A bare JWT header segment is still redacted."""
    text = "tok eyJhbGciOiJIUzI1NiJ9.eyJ0ZXN0IjoidGVzdCJ9.abc123"
    result = sanitize(text)
    assert "eyJhbGciOiJIUzI1NiJ9" not in result


def test_sanitize_still_redacts_high_entropy_token_after_relaxation() -> None:
    """A contiguous high-entropy slash-bearing secret is still redacted."""
    secret = "AbCdEfGhIjKlMnOp/QrStUvWxYz012345/AbCdEfGhIjKl"
    result = sanitize(f"branch=feature/JIRA-1 creds={secret}")
    assert secret not in result
    assert "feature/JIRA-1" in result


def test_sanitize_redacts_pem_private_key_block() -> None:
    """A PEM private-key block is fully redacted (markers + body)."""
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQD1\n"
        "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOP\n"
        "-----END RSA PRIVATE KEY-----"
    )
    result = sanitize(f"key:\n{pem}")
    assert "MIIEvgIBADANBgkqhkiG" not in result
    assert "BEGIN RSA PRIVATE KEY" not in result
    assert "[REDACTED]" in result


def test_sanitize_redacts_short_pem_private_key_block() -> None:
    """A short-bodied PEM private-key block is still redacted."""
    pem = "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    result = sanitize(pem)
    assert "abc" not in result
    assert "PRIVATE KEY" not in result
    assert "[REDACTED]" in result


def test_sanitize_url_password_with_at_sign() -> None:
    """A URL password containing '@' is fully redacted, not leaked in part."""
    result = sanitize("mysql://user:p@ss@host/db")
    assert "p@ss" not in result
    assert "user" not in result
    assert result == "[REDACTED]host/db"


def test_sanitize_url_simple_credential() -> None:
    """Standard scheme://user:pass@host credentials are redacted."""
    result = sanitize("amqp://guest:guest@localhost:5672/vhost")
    assert "guest:guest" not in result
    assert result == "[REDACTED]localhost:5672/vhost"


def test_sanitize_url_without_credentials_preserved() -> None:
    """A plain URL with no userinfo is left untouched."""
    text = "see https://example.com/path here"
    assert sanitize(text) == text


def test_sanitize_jwt() -> None:
    """JSON Web Tokens are redacted even when the header is low-entropy."""
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abc-_123XYZ"
    result = sanitize(f"token {jwt} done")
    assert jwt not in result
    assert "eyJ" not in result
