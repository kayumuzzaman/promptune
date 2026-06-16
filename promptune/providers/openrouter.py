"""OpenRouter provider using httpx."""

from __future__ import annotations

from typing import Any

import httpx

from promptune.providers import BaseProvider, ProviderError, ProviderRegistry


class OpenRouterProvider(BaseProvider):
    """AI provider using the OpenRouter API via httpx."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 30.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.max_tokens = max_tokens
        self.base_url = base_url
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/promptune",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    def enhance(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to OpenRouter and return enhanced version."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        if self.max_tokens is not None:
            body["max_tokens"] = self.max_tokens
        try:
            with httpx.Client(
                headers=self._headers, timeout=self._timeout
            ) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(str(e)) from e

        choices = data.get("choices", [])
        if not choices:
            raise ProviderError(
                "Empty response from OpenRouter API"
            )

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ProviderError(
                "Empty response from OpenRouter API"
            )

        return str(content)


def register(registry: ProviderRegistry) -> None:
    """Register the OpenRouter provider."""
    registry.register("openrouter", OpenRouterProvider)
