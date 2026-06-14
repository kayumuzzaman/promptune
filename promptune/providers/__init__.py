"""Provider base class and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProviderError(Exception):
    """Raised when a provider encounters an error."""


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
