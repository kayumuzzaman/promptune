"""Local LLM provider: OpenAI-compatible HTTP client.

Supports any tool that exposes an OpenAI-compatible /v1/chat/completions
endpoint: Ollama, LM Studio, llama.cpp, vLLM, LocalAI, Jan, etc.
"""

from __future__ import annotations

from typing import Any

import httpx

from promptune.providers import (
    BaseProvider,
    ProviderError,
    ProviderRegistry,
)


class LocalProvider(BaseProvider):
    """AI provider using a local OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        api_key: str = "",
        timeout: float = 30.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.max_tokens = max_tokens
        self.host = host.rstrip("/")
        self._headers: dict[str, str] = {
            "Content-Type": "application/json"
        }
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._timeout = timeout

    def enhance(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to local LLM and return enhanced text."""
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
                    f"{self.host}/v1/chat/completions",
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to local LLM at {self.host}. "
                f"Is your local LLM server running? Error: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Timeout connecting to local LLM at "
                f"{self.host}. The model may be loading "
                f"(cold start). Error: {e}"
            ) from e
        except Exception as e:
            raise ProviderError(str(e)) from e

        choices = data.get("choices", [])
        if not choices:
            raise ProviderError("Empty response from local LLM")

        content = (
            choices[0].get("message", {}).get("content", "")
        )
        if not content:
            raise ProviderError("Empty response from local LLM")

        return str(content)


def register(registry: ProviderRegistry) -> None:
    """Register the local LLM provider."""
    registry.register("local", LocalProvider)
