"""OpenAI provider using the OpenAI SDK."""

from __future__ import annotations

from typing import Any

import openai as openai_sdk

from promptune.providers import BaseProvider, ProviderError, ProviderRegistry


class OpenAIProvider(BaseProvider):
    """AI provider using the OpenAI API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.max_tokens = max_tokens
        self._client = openai_sdk.OpenAI(
            api_key=api_key,
            timeout=timeout,
        )

    def enhance(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to OpenAI and return enhanced version."""
        extra: dict[str, Any] = {}
        if self.max_tokens is not None:
            extra["max_tokens"] = self.max_tokens
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                **extra,
            )
        except Exception as e:
            raise ProviderError(str(e)) from e

        if not response.choices:
            raise ProviderError("Empty response from OpenAI API")

        content = response.choices[0].message.content
        if not content:
            raise ProviderError("Empty response from OpenAI API")

        return content


def register(registry: ProviderRegistry) -> None:
    """Register the OpenAI provider."""
    registry.register("openai", OpenAIProvider)
