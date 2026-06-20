"""Step 5: OpenRouter Provider — tests."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from promptune.providers import BaseProvider, ProviderError, ProviderRegistry
from promptune.providers.openrouter import OpenRouterProvider


def _mock_httpx_client(
    mocker: MockerFixture, mock_response: MagicMock
) -> tuple[MagicMock, MagicMock]:
    """Patch httpx.Client context manager, return (mock_cls, mock_client)."""
    mock_client = mocker.MagicMock()
    mock_client.post.return_value = mock_response
    mock_cls = mocker.patch(
        "promptune.providers.openrouter.httpx.Client"
    )
    mock_cls.return_value.__enter__ = mocker.MagicMock(
        return_value=mock_client
    )
    mock_cls.return_value.__exit__ = mocker.MagicMock(
        return_value=False
    )
    return mock_cls, mock_client


def test_openrouter_provider_implements_base() -> None:
    """OpenRouterProvider is a subclass of BaseProvider."""
    assert issubclass(OpenRouterProvider, BaseProvider)


def test_openrouter_enhance_returns_string(
    mocker: MockerFixture,
) -> None:
    """Mock httpx returns enhanced text."""
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Enhanced prompt"}}]
    }
    mock_response.raise_for_status = mocker.MagicMock()

    _mock_httpx_client(mocker, mock_response)

    provider = OpenRouterProvider(
        api_key="test-key",
        model="anthropic/claude-sonnet-4-20250514",
        base_url="https://openrouter.ai/api/v1",
    )
    result = provider.enhance("rough prompt", "system instructions")

    assert isinstance(result, str)
    assert result == "Enhanced prompt"


def test_openrouter_sends_correct_headers(
    mocker: MockerFixture,
) -> None:
    """Verify Authorization header stored on provider."""
    provider = OpenRouterProvider(
        api_key="my-key",
        model="m",
        base_url="https://openrouter.ai/api/v1",
    )
    assert provider._headers["Authorization"] == "Bearer my-key"
    assert "HTTP-Referer" in provider._headers


def test_openrouter_sends_correct_body(
    mocker: MockerFixture,
) -> None:
    """Verify model and messages in request body."""
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "result"}}]
    }
    mock_response.raise_for_status = mocker.MagicMock()

    _, mock_client = _mock_httpx_client(mocker, mock_response)

    provider = OpenRouterProvider(
        api_key="k",
        model="my-model",
        base_url="https://openrouter.ai/api/v1",
    )
    provider.enhance("my prompt", "my system")

    call_kwargs = mock_client.post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get(
        "json"
    )
    assert body["model"] == "my-model"
    assert body["messages"] == [
        {"role": "system", "content": "my system"},
        {"role": "user", "content": "my prompt"},
    ]


def test_openrouter_api_error_handling(
    mocker: MockerFixture,
) -> None:
    """Non-200 response raises ProviderError."""
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.side_effect = Exception(
        "Server Error"
    )

    _mock_httpx_client(mocker, mock_response)

    provider = OpenRouterProvider(
        api_key="k", model="m", base_url="https://openrouter.ai/api/v1"
    )
    with pytest.raises(ProviderError, match="Server Error"):
        provider.enhance("prompt", "system")


def test_openrouter_error_redacts_base_url_userinfo(
    mocker: MockerFixture,
) -> None:
    """base_url credentials must not leak through error messages."""
    base_url = "https://user:secret@router.example/api/v1"
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.side_effect = Exception(
        f"connect error to {base_url}/chat/completions"
    )
    _mock_httpx_client(mocker, mock_response)

    provider = OpenRouterProvider(api_key="k", model="m", base_url=base_url)
    with pytest.raises(ProviderError) as exc:
        provider.enhance("prompt", "system")
    assert "secret" not in str(exc.value)
    assert "user:secret" not in str(exc.value)


def test_openrouter_timeout_handling(
    mocker: MockerFixture,
) -> None:
    """Timeout raises ProviderError."""
    import httpx

    mock_client = mocker.MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException("timed out")
    mock_cls = mocker.patch(
        "promptune.providers.openrouter.httpx.Client"
    )
    mock_cls.return_value.__enter__ = mocker.MagicMock(
        return_value=mock_client
    )
    mock_cls.return_value.__exit__ = mocker.MagicMock(
        return_value=False
    )

    provider = OpenRouterProvider(
        api_key="k", model="m", base_url="https://openrouter.ai/api/v1"
    )
    with pytest.raises(ProviderError, match="timed out"):
        provider.enhance("prompt", "system")


@pytest.mark.parametrize(
    "payload",
    [
        ["not", "a", "dict"],          # top-level JSON array
        "a bare string",               # top-level JSON string
        {"choices": "nonsense"},       # choices not a list
        {"choices": ["plain string"]},  # choice not a dict
        {"choices": [{"message": "oops"}]},  # message not a dict
        {"choices": []},               # empty choices
    ],
)
def test_openrouter_malformed_response_raises_provider_error(
    mocker: MockerFixture, payload: object
) -> None:
    """A malformed API body degrades to ProviderError, never AttributeError."""
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status = mocker.MagicMock()
    _mock_httpx_client(mocker, mock_response)

    provider = OpenRouterProvider(
        api_key="k", model="m", base_url="https://openrouter.ai/api/v1"
    )
    with pytest.raises(ProviderError):
        provider.enhance("prompt", "system")


def test_openrouter_registered_in_registry() -> None:
    """'openrouter' name in provider registry."""
    from promptune.providers.openrouter import register

    registry = ProviderRegistry()
    register(registry)
    assert "openrouter" in registry.list()
    assert registry.get("openrouter") is OpenRouterProvider
