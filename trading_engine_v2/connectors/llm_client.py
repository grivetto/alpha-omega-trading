"""OpenAI-compatible LLM client for local inference (Ollama / LM Studio)."""
from __future__ import annotations
import json
import time
from typing import Optional

import httpx

from core.config import settings
from core.exceptions import LLMInferenceError, LLMTimeoutError
from core.logger import AgentLogger

log = AgentLogger.get("llm_client")


class LLMClient:
    """Asynchronous client for OpenAI-compatible local LLM endpoints."""

    def __init__(self, config=None):
        self.cfg = config or settings.llm
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.cfg.endpoint,
                timeout=self.cfg.timeout,
                headers={"Authorization": f"Bearer {self.cfg.api_key}"},
            )
        return self._client

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Send a chat completion request to the local LLM endpoint.

        Args:
            system_prompt: System-level instruction for the model.
            user_prompt: The user's query / market data to analyse.
            max_tokens: Override default max tokens.
            temperature: Override default temperature.

        Returns:
            The model's text response.

        Raises:
            LLMInferenceError: On non-2xx response or malformed reply.
            LLMTimeoutError: When the endpoint doesn't respond in time.
        """
        client = await self._get_client()
        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens or self.cfg.max_tokens,
            "temperature": temperature or self.cfg.temperature,
            "stream": False,
        }

        last_error = None
        for attempt in range(1, self.cfg.max_retries + 1):
            try:
                log.debug("LLM call attempt %d/%d", attempt, self.cfg.max_retries,
                          model=self.cfg.model, tokens=payload["max_tokens"])

                resp = await client.post("/chat/completions", json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    log.info("LLM response received", chars=len(content))
                    return content.strip()

                raise LLMInferenceError(
                    f"Non-200 response: {resp.text[:200]}",
                    endpoint=self.cfg.endpoint,
                    status_code=resp.status_code,
                )

            except httpx.TimeoutException as e:
                last_error = LLMTimeoutError(
                    endpoint=self.cfg.endpoint, timeout=self.cfg.timeout
                )
                log.warn("LLM timeout (attempt %d)", attempt)
                if attempt < self.cfg.max_retries:
                    wait = 2 ** attempt
                    log.info("Retrying in %ds...", wait)
                    await asyncio.sleep(wait)

            except httpx.RequestError as e:
                last_error = LLMInferenceError(
                    f"Network error: {e}", endpoint=self.cfg.endpoint
                )
                log.error("LLM request failed (attempt %d): %s", attempt, e)
                if attempt < self.cfg.max_retries:
                    await asyncio.sleep(2 ** attempt)

            except (KeyError, IndexError, json.JSONDecodeError) as e:
                last_error = LLMInferenceError(
                    f"Malformed response: {e}", endpoint=self.cfg.endpoint
                )
                log.error("LLM parse error (attempt %d): %s", attempt, e)
                break  # No point retrying a parse error

        raise last_error or LLMInferenceError("All retries exhausted")

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


import asyncio  # noqa: E402 (needed for sleep in retry logic)
