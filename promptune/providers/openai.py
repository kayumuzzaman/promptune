"""OpenAI provider using the OpenAI SDK."""

from __future__ import annotations

import re
from typing import Any

import openai as openai_sdk

from promptune.providers import (
    BaseProvider,
    ProviderError,
    ProviderRegistry,
    redact_secrets,
)


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
            # Reasoning models (o1/o3/o4... and gpt-5-class) reject
            # `max_tokens` and require `max_completion_tokens`; classic chat
            # models still take the old parameter, so pick by model name.
            param = (
                "max_completion_tokens"
                if re.match(r"(o\d|gpt-5)", self.model, re.IGNORECASE)
                else "max_tokens"
            )
            extra[param] = self.max_tokens
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
            raise ProviderError(
                redact_secrets(str(e), self.api_key)
            ) from e

        if not response.choices:
            raise ProviderError("Empty response from OpenAI API")

        content = response.choices[0].message.content
        if not content:
            raise ProviderError("Empty response from OpenAI API")

        return str(content)


def register(registry: ProviderRegistry) -> None:
    """Register the OpenAI provider."""
    registry.register("openai", OpenAIProvider)
