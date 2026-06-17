"""Step 3: Claude Provider — tests."""

import pytest
from anthropic.types import TextBlock
from pytest_mock import MockerFixture

from promptune.providers import BaseProvider, ProviderError, ProviderRegistry
from promptune.providers.anthropic import ClaudeProvider


def _text_block(text: str) -> TextBlock:
    """Create a real TextBlock for mocking responses."""
    return TextBlock(type="text", text=text)


def test_claude_provider_implements_base() -> None:
    """ClaudeProvider is a subclass of BaseProvider."""
    assert issubclass(ClaudeProvider, BaseProvider)


def test_claude_enhance_returns_string(mocker: MockerFixture) -> None:
    """Mock API returns enhanced text."""
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mocker.MagicMock(
        content=[_text_block("Enhanced prompt here")]
    )
    mocker.patch(
        "promptune.providers.anthropic.anthropic.Anthropic",
        return_value=mock_client,
    )

    provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-20250514")
    result = provider.enhance("rough prompt", "system instructions")

    assert isinstance(result, str)
    assert result == "Enhanced prompt here"


def test_claude_enhance_sends_correct_params(
    mocker: MockerFixture,
) -> None:
    """Verify model, messages, system prompt sent correctly."""
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mocker.MagicMock(
        content=[_text_block("result")]
    )
    mocker.patch(
        "promptune.providers.anthropic.anthropic.Anthropic",
        return_value=mock_client,
    )

    provider = ClaudeProvider(api_key="test-key", model="my-model")
    provider.enhance("my prompt", "my system")

    mock_client.messages.create.assert_called_once_with(
        model="my-model",
        max_tokens=4096,
        system="my system",
        messages=[{"role": "user", "content": "my prompt"}],
    )


def test_claude_uses_configured_max_tokens(mocker: MockerFixture) -> None:
    """A configured max_tokens is forwarded to the API."""
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mocker.MagicMock(
        content=[_text_block("result")]
    )
    mocker.patch(
        "promptune.providers.anthropic.anthropic.Anthropic",
        return_value=mock_client,
    )

    provider = ClaudeProvider(
        api_key="k", model="m", max_tokens=400
    )
    provider.enhance("p", "s")

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["max_tokens"] == 400


def test_claude_api_error_handling(mocker: MockerFixture) -> None:
    """API error raises ProviderError."""
    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = Exception("API failed")
    mocker.patch(
        "promptune.providers.anthropic.anthropic.Anthropic",
        return_value=mock_client,
    )

    provider = ClaudeProvider(api_key="test-key", model="m")
    with pytest.raises(ProviderError, match="API failed"):
        provider.enhance("prompt", "system")


def test_claude_empty_response_handling(
    mocker: MockerFixture,
) -> None:
    """Empty response raises ProviderError."""
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mocker.MagicMock(content=[])
    mocker.patch(
        "promptune.providers.anthropic.anthropic.Anthropic",
        return_value=mock_client,
    )

    provider = ClaudeProvider(api_key="test-key", model="m")
    with pytest.raises(ProviderError, match="[Ee]mpty"):
        provider.enhance("prompt", "system")


def test_claude_empty_textblock_raises(mocker: MockerFixture) -> None:
    """A TextBlock with empty text is treated as an empty response."""
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = mocker.MagicMock(
        content=[_text_block("   ")]
    )
    mocker.patch(
        "promptune.providers.anthropic.anthropic.Anthropic",
        return_value=mock_client,
    )

    provider = ClaudeProvider(api_key="test-key", model="m")
    with pytest.raises(ProviderError, match="[Ee]mpty"):
        provider.enhance("prompt", "system")


def test_claude_registered_in_registry() -> None:
    """'claude' name in provider registry."""
    from promptune.providers.anthropic import register

    registry = ProviderRegistry()
    register(registry)
    assert "claude" in registry.list()
    assert registry.get("claude") is ClaudeProvider
