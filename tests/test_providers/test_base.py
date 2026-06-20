"""Step 2: Provider Base Class — tests."""

import pytest

from promptune.providers import (
    BaseProvider,
    ProviderNotFoundError,
    ProviderRegistry,
    redact_url_userinfo,
    redact_url_userinfo_in_text,
)


class FakeProvider(BaseProvider):
    """Concrete provider for testing."""

    def enhance(self, prompt: str, system_prompt: str) -> str:
        return f"enhanced: {prompt}"


def test_base_provider_is_abstract() -> None:
    """Cannot instantiate BaseProvider directly."""
    with pytest.raises(TypeError):
        BaseProvider(api_key="k", model="m")  # type: ignore[abstract]


class OtherProvider(BaseProvider):
    def enhance(self, prompt: str, system_prompt: str) -> str:
        return prompt


def test_registry_warns_on_clobber() -> None:
    """Re-registering a name with a different class warns; same class is silent."""
    registry = ProviderRegistry()
    registry.register("p", FakeProvider)
    registry.register("p", FakeProvider)  # identical: no warning
    with pytest.warns(UserWarning, match="Overwriting"):
        registry.register("p", OtherProvider)
    assert registry.get("p") is OtherProvider


def test_base_provider_has_enhance_method() -> None:
    """ABC defines enhance() method."""
    assert hasattr(BaseProvider, "enhance")
    provider = FakeProvider(api_key="k", model="m")
    result = provider.enhance("hello", "system")
    assert result == "enhanced: hello"


def test_registry_register() -> None:
    """Register a provider by name."""
    registry = ProviderRegistry()
    registry.register("fake", FakeProvider)
    assert "fake" in registry.list()


def test_registry_get_known() -> None:
    """Retrieve registered provider class."""
    registry = ProviderRegistry()
    registry.register("fake", FakeProvider)
    cls = registry.get("fake")
    assert cls is FakeProvider


def test_registry_get_unknown() -> None:
    """Unknown name raises ProviderNotFoundError."""
    registry = ProviderRegistry()
    with pytest.raises(ProviderNotFoundError, match="nonexistent"):
        registry.get("nonexistent")


def test_registry_list() -> None:
    """List all registered provider names."""
    registry = ProviderRegistry()
    registry.register("a", FakeProvider)
    registry.register("b", FakeProvider)
    assert sorted(registry.list()) == ["a", "b"]


def test_base_provider_optional_api_key() -> None:
    """BaseProvider can be instantiated without api_key."""
    provider = FakeProvider(model="test-model")
    assert provider.api_key == ""
    assert provider.model == "test-model"


def test_base_provider_optional_model() -> None:
    """BaseProvider can be instantiated without model."""
    provider = FakeProvider(api_key="key")
    assert provider.model == ""


def test_provider_from_config() -> None:
    """Create provider instance from config dict."""
    registry = ProviderRegistry()
    registry.register("fake", FakeProvider)
    config = {"api_key": "test-key", "model": "test-model"}
    provider = registry.create("fake", config)
    assert isinstance(provider, FakeProvider)
    assert provider.api_key == "test-key"
    assert provider.model == "test-model"


def test_redact_url_userinfo_basic() -> None:
    """user:pass@ is stripped from a URL."""
    assert (
        redact_url_userinfo("http://user:secret@host:11434/v1")
        == "http://[REDACTED]@host:11434/v1"
    )


def test_redact_url_userinfo_no_userinfo_unchanged() -> None:
    """A URL without credentials is returned unchanged."""
    assert redact_url_userinfo("http://host:11434") == "http://host:11434"


def test_redact_url_userinfo_no_scheme_unchanged() -> None:
    """A bare value without a scheme is not treated as a URL."""
    assert redact_url_userinfo("user@host") == "user@host"


def test_redact_in_text_robust_to_scheme_case_normalization() -> None:
    """httpx lowercases the scheme; redaction must still catch credentials."""
    cfg_url = "HTTP://user:secret@localhost:11434"
    err = "connect failed to http://user:secret@localhost:11434/v1/chat"
    out = redact_url_userinfo_in_text(err, cfg_url)
    assert "secret" not in out
    assert "[REDACTED]" in out


def test_redact_in_text_robust_to_host_case_normalization() -> None:
    """Host-case normalization in error text must not defeat redaction."""
    cfg_url = "http://user:secret@MyHost:11434"
    err = "fail http://user:secret@myhost:11434/x"
    assert "secret" not in redact_url_userinfo_in_text(err, cfg_url)


def test_redact_in_text_redacts_unhinted_url_userinfo() -> None:
    """Any scheme://user:pass@host in text is redacted, even without a hint."""
    err = "secondary https://admin:pw123@other:8080/api error"
    out = redact_url_userinfo_in_text(err)
    assert "pw123" not in out
    assert "admin" not in out


def test_redact_in_text_leaves_bare_email_untouched() -> None:
    """A bare email (no scheme) is not URL userinfo and must be preserved."""
    err = "contact user@example.com about the failure"
    assert redact_url_userinfo_in_text(err) == err


def test_redact_in_text_is_linear_on_large_input() -> None:
    """Guard against O(n^2) regression: a large error body must stay fast.

    The bounded scheme run keeps this linear (~tens of ms for 500k chars); an
    unbounded scheme quantifier degraded to ~20s for 200k chars. The 5s bound
    is a ~160x margin over the real cost, so it only trips on a true blowup.
    """
    import time

    big = "connection error: " + ("a" * 500_000)
    start = time.perf_counter()
    out = redact_url_userinfo_in_text(big, "http://u:p@host")
    assert out == big  # no false redaction
    assert time.perf_counter() - start < 5.0
