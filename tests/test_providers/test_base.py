"""Step 2: Provider Base Class — tests."""

import pytest

from promptune.providers import (
    BaseProvider,
    ProviderNotFoundError,
    ProviderRegistry,
)


class FakeProvider(BaseProvider):
    """Concrete provider for testing."""

    def enhance(self, prompt: str, system_prompt: str) -> str:
        return f"enhanced: {prompt}"


def test_base_provider_is_abstract() -> None:
    """Cannot instantiate BaseProvider directly."""
    with pytest.raises(TypeError):
        BaseProvider(api_key="k", model="m")  # type: ignore[abstract]


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
