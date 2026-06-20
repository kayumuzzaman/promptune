"""Provider base class and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlsplit, urlunsplit


class ProviderError(Exception):
    """Raised when a provider encounters an error."""


def redact_secrets(message: str, *secrets: str) -> str:
    """Replace any known secret values in an error message with a marker."""
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message


def redact_url_userinfo(value: str) -> str:
    """Redact username/password embedded in URLs."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or "@" not in parsed.netloc:
        return value
    _, host = parsed.netloc.rsplit("@", 1)
    return urlunsplit((
        parsed.scheme,
        f"[REDACTED]@{host}",
        parsed.path,
        parsed.query,
        parsed.fragment,
    ))


def redact_url_userinfo_in_text(text: str, *urls: str) -> str:
    """Redact URL userinfo for each known URL occurrence in text."""
    for url in urls:
        redacted = redact_url_userinfo(url)
        if redacted != url:
            text = text.replace(url, redacted)
    return text


class ProviderNotFoundError(Exception):
    """Raised when a requested provider is not registered."""


class BaseProvider(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def enhance(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to AI and return enhanced version."""


class ProviderRegistry:
    """Registry for provider classes."""

    def __init__(self) -> None:
        self._providers: dict[str, type[BaseProvider]] = {}

    def register(self, name: str, cls: type[BaseProvider]) -> None:
        """Register a provider class by name."""
        existing = self._providers.get(name)
        if existing is not None and existing is not cls:
            import warnings

            warnings.warn(
                f"Overwriting registered provider {name!r}: "
                f"{existing.__name__} -> {cls.__name__}",
                stacklevel=2,
            )
        self._providers[name] = cls

    def get(self, name: str) -> type[BaseProvider]:
        """Get a provider class by name."""
        if name not in self._providers:
            raise ProviderNotFoundError(
                f"Provider '{name}' not found. "
                f"Available: {', '.join(sorted(self._providers))}"
            )
        return self._providers[name]

    def list(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def create(
        self, name: str, config: dict[str, Any]
    ) -> BaseProvider:
        """Create a provider instance from config."""
        cls = self.get(name)
        return cls(**config)
