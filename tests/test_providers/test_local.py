"""Local LLM Provider tests."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from promptune.providers import BaseProvider, ProviderError
from promptune.providers.local import LocalProvider


def test_local_provider_implements_base() -> None:
    """LocalProvider is subclass of BaseProvider."""
    assert issubclass(LocalProvider, BaseProvider)


def test_local_provider_init() -> None:
    """LocalProvider stores host and model."""
    provider = LocalProvider(
        model="qwen2.5:3b", host="http://localhost:11434"
    )
    assert provider.model == "qwen2.5:3b"
    assert provider.host == "http://localhost:11434"
    assert provider.api_key == ""


def test_local_provider_init_with_api_key() -> None:
    """LocalProvider accepts optional api_key."""
    provider = LocalProvider(
        model="qwen2.5:3b",
        host="http://localhost:11434",
        api_key="dummy-key",
    )
    assert provider.api_key == "dummy-key"


def _mock_httpx_client(
    mocker: MockerFixture, mock_response: MagicMock
) -> MagicMock:
    """Patch httpx.Client so the context manager returns a mock with post()."""
    mock_client = mocker.MagicMock()
    mock_client.post.return_value = mock_response
    mock_cls = mocker.patch(
        "promptune.providers.local.httpx.Client"
    )
    mock_cls.return_value.__enter__ = mocker.MagicMock(
        return_value=mock_client
    )
    mock_cls.return_value.__exit__ = mocker.MagicMock(
        return_value=False
    )
    return mock_client


def test_local_enhance_returns_string(
    mocker: MockerFixture,
) -> None:
    """Mock API returns enhanced text."""
    provider = LocalProvider(
        model="qwen2.5:3b", host="http://localhost:11434"
    )

    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": "Enhanced prompt text"}}
        ],
    }
    mock_response.raise_for_status = mocker.MagicMock()

    _mock_httpx_client(mocker, mock_response)

    result = provider.enhance("rough prompt", "system prompt")
    assert result == "Enhanced prompt text"


def test_local_enhance_sends_correct_body(
    mocker: MockerFixture,
) -> None:
    """Verify model, messages in request body."""
    provider = LocalProvider(
        model="qwen2.5:3b", host="http://localhost:11434"
    )

    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "result"}}],
    }
    mock_response.raise_for_status = mocker.MagicMock()

    mock_client = _mock_httpx_client(mocker, mock_response)

    provider.enhance("test prompt", "system prompt")

    call_kwargs = mock_client.post.call_args
    url = str(call_kwargs)
    assert "v1/chat/completions" in url
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get(
        "json"
    )
    assert body["model"] == "qwen2.5:3b"
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"


def test_local_api_error_handling(
    mocker: MockerFixture,
) -> None:
    """Non-200 response raises ProviderError."""
    provider = LocalProvider(
        model="qwen2.5:3b", host="http://localhost:11434"
    )

    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.side_effect = Exception(
        "500 Server Error"
    )

    _mock_httpx_client(mocker, mock_response)

    with pytest.raises(ProviderError, match="500"):
        provider.enhance("prompt", "system")


def test_local_timeout_handling(mocker: MockerFixture) -> None:
    """Timeout raises ProviderError."""
    import httpx

    provider = LocalProvider(
        model="qwen2.5:3b", host="http://localhost:11434"
    )

    mock_client = mocker.MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException(
        "Connection timed out"
    )
    mock_cls = mocker.patch(
        "promptune.providers.local.httpx.Client"
    )
    mock_cls.return_value.__enter__ = mocker.MagicMock(
        return_value=mock_client
    )
    mock_cls.return_value.__exit__ = mocker.MagicMock(
        return_value=False
    )

    with pytest.raises(ProviderError, match="[Tt]imeout|timed out"):
        provider.enhance("prompt", "system")


def test_local_connection_refused(mocker: MockerFixture) -> None:
    """Connection refused raises ProviderError."""
    import httpx

    provider = LocalProvider(
        model="qwen2.5:3b", host="http://localhost:11434"
    )

    mock_client = mocker.MagicMock()
    mock_client.post.side_effect = httpx.ConnectError(
        "Connection refused"
    )
    mock_cls = mocker.patch(
        "promptune.providers.local.httpx.Client"
    )
    mock_cls.return_value.__enter__ = mocker.MagicMock(
        return_value=mock_client
    )
    mock_cls.return_value.__exit__ = mocker.MagicMock(
        return_value=False
    )

    with pytest.raises(
        ProviderError, match="[Cc]onnect|refused|unreachable"
    ):
        provider.enhance("prompt", "system")


def test_local_errors_redact_host_userinfo(
    mocker: MockerFixture,
) -> None:
    """Credentialed local LLM URLs are redacted from user-facing errors."""
    import httpx

    provider = LocalProvider(
        model="qwen2.5:3b", host="http://user:pass@localhost:11434"
    )
    mock_client = mocker.MagicMock()
    mock_client.post.side_effect = httpx.ConnectError(
        "Cannot connect to http://user:pass@localhost:11434"
    )
    mock_cls = mocker.patch(
        "promptune.providers.local.httpx.Client"
    )
    mock_cls.return_value.__enter__ = mocker.MagicMock(
        return_value=mock_client
    )
    mock_cls.return_value.__exit__ = mocker.MagicMock(
        return_value=False
    )

    with pytest.raises(ProviderError) as exc:
        provider.enhance("prompt", "system")

    message = str(exc.value)
    assert "user:pass" not in message
    assert "localhost:11434" in message


def test_local_empty_response_handling(
    mocker: MockerFixture,
) -> None:
    """Empty response raises ProviderError."""
    provider = LocalProvider(
        model="qwen2.5:3b", host="http://localhost:11434"
    )

    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"choices": []}
    mock_response.raise_for_status = mocker.MagicMock()

    _mock_httpx_client(mocker, mock_response)

    with pytest.raises(ProviderError, match="[Ee]mpty"):
        provider.enhance("prompt", "system")


@pytest.mark.parametrize(
    "payload",
    [
        ["not", "a", "dict"],
        "a bare string",
        {"choices": "nonsense"},
        {"choices": ["plain string"]},
        {"choices": [{"message": "oops"}]},
    ],
)
def test_local_malformed_response_raises_provider_error(
    mocker: MockerFixture, payload: object
) -> None:
    """A malformed local-LLM body degrades to ProviderError, not AttributeError."""
    provider = LocalProvider(
        model="qwen2.5:3b", host="http://localhost:11434"
    )
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status = mocker.MagicMock()
    _mock_httpx_client(mocker, mock_response)

    with pytest.raises(ProviderError):
        provider.enhance("prompt", "system")
