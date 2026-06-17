"""Step 4: OpenAI Provider — tests."""

import pytest
from pytest_mock import MockerFixture

from promptune.providers import BaseProvider, ProviderError, ProviderRegistry
from promptune.providers.openai import OpenAIProvider


def test_openai_provider_implements_base() -> None:
    """OpenAIProvider is a subclass of BaseProvider."""
    assert issubclass(OpenAIProvider, BaseProvider)


def test_openai_enhance_returns_string(mocker: MockerFixture) -> None:
    """Mock API returns enhanced text."""
    mock_client = mocker.MagicMock()
    mock_choice = mocker.MagicMock()
    mock_choice.message.content = "Enhanced prompt here"
    mock_client.chat.completions.create.return_value = mocker.MagicMock(
        choices=[mock_choice]
    )
    mocker.patch(
        "promptune.providers.openai.openai_sdk.OpenAI",
        return_value=mock_client,
    )

    provider = OpenAIProvider(api_key="test-key", model="gpt-4o")
    result = provider.enhance("rough prompt", "system instructions")

    assert isinstance(result, str)
    assert result == "Enhanced prompt here"


def test_openai_enhance_sends_correct_params(
    mocker: MockerFixture,
) -> None:
    """Verify model, messages sent correctly."""
    mock_client = mocker.MagicMock()
    mock_choice = mocker.MagicMock()
    mock_choice.message.content = "result"
    mock_client.chat.completions.create.return_value = mocker.MagicMock(
        choices=[mock_choice]
    )
    mocker.patch(
        "promptune.providers.openai.openai_sdk.OpenAI",
        return_value=mock_client,
    )

    provider = OpenAIProvider(api_key="test-key", model="my-model")
    provider.enhance("my prompt", "my system")

    mock_client.chat.completions.create.assert_called_once_with(
        model="my-model",
        messages=[
            {"role": "system", "content": "my system"},
            {"role": "user", "content": "my prompt"},
        ],
    )


def _enhance_with_cap(mocker: MockerFixture, model: str) -> dict:
    """Run enhance with a token cap and return the kwargs sent to the SDK."""
    mock_client = mocker.MagicMock()
    mock_choice = mocker.MagicMock()
    mock_choice.message.content = "result"
    mock_client.chat.completions.create.return_value = mocker.MagicMock(
        choices=[mock_choice]
    )
    mocker.patch(
        "promptune.providers.openai.openai_sdk.OpenAI",
        return_value=mock_client,
    )
    provider = OpenAIProvider(api_key="test-key", model=model, max_tokens=128)
    provider.enhance("p", "s")
    return mock_client.chat.completions.create.call_args.kwargs


def test_openai_chat_model_uses_max_tokens(mocker: MockerFixture) -> None:
    """Classic chat models receive the legacy max_tokens parameter."""
    kwargs = _enhance_with_cap(mocker, "gpt-4o-mini")
    assert kwargs["max_tokens"] == 128
    assert "max_completion_tokens" not in kwargs


def test_openai_o_series_uses_max_completion_tokens(
    mocker: MockerFixture,
) -> None:
    """o-series reasoning models receive max_completion_tokens instead."""
    kwargs = _enhance_with_cap(mocker, "o3-mini")
    assert kwargs["max_completion_tokens"] == 128
    assert "max_tokens" not in kwargs


def test_openai_gpt5_uses_max_completion_tokens(
    mocker: MockerFixture,
) -> None:
    """gpt-5-class reasoning models also require max_completion_tokens."""
    kwargs = _enhance_with_cap(mocker, "gpt-5-mini")
    assert kwargs["max_completion_tokens"] == 128
    assert "max_tokens" not in kwargs


def test_openai_api_error_handling(mocker: MockerFixture) -> None:
    """API error raises ProviderError."""
    mock_client = mocker.MagicMock()
    mock_client.chat.completions.create.side_effect = Exception(
        "API failed"
    )
    mocker.patch(
        "promptune.providers.openai.openai_sdk.OpenAI",
        return_value=mock_client,
    )

    provider = OpenAIProvider(api_key="test-key", model="m")
    with pytest.raises(ProviderError, match="API failed"):
        provider.enhance("prompt", "system")


def test_openai_empty_response_handling(
    mocker: MockerFixture,
) -> None:
    """Empty response raises ProviderError."""
    mock_client = mocker.MagicMock()
    mock_client.chat.completions.create.return_value = mocker.MagicMock(
        choices=[]
    )
    mocker.patch(
        "promptune.providers.openai.openai_sdk.OpenAI",
        return_value=mock_client,
    )

    provider = OpenAIProvider(api_key="test-key", model="m")
    with pytest.raises(ProviderError, match="[Ee]mpty"):
        provider.enhance("prompt", "system")


def test_openai_registered_in_registry() -> None:
    """'openai' name in provider registry."""
    from promptune.providers.openai import register

    registry = ProviderRegistry()
    register(registry)
    assert "openai" in registry.list()
    assert registry.get("openai") is OpenAIProvider
