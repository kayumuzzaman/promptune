"""Claude provider using the Anthropic SDK."""

from __future__ import annotations

from typing import Any

import anthropic
from anthropic.types import TextBlock

from promptune.providers import (
    BaseProvider,
    ProviderError,
    ProviderRegistry,
    redact_secrets,
)


class ClaudeProvider(BaseProvider):
    """AI provider using the Anthropic Claude API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.max_tokens = max_tokens or 4096
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout,
        )

    def enhance(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to Claude and return enhanced version."""
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise ProviderError(
                redact_secrets(str(e), self.api_key)
            ) from e

        if not response.content:
            raise ProviderError("Empty response from Claude API")

        block = response.content[0]
        if not isinstance(block, TextBlock):
            raise ProviderError("Empty response from Claude API")
        return block.text


def register(registry: ProviderRegistry) -> None:
    """Register the Claude provider."""
    registry.register("claude", ClaudeProvider)
