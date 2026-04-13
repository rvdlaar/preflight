"""
Preflight LLM client abstraction.

Supports Ollama (local dev) and NVIDIA NIM (production).
The pipeline doesn't care which backend — same interface.

Design decisions:
- Protocol-based, not inheritance — duck typing over class hierarchies
- Async first — LLM calls are I/O bound
- Streaming support for long responses (deep mode)
- Token counting for cost tracking
- Retry with backoff — LLM calls fail transiently
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Protocol


# ---------------------------------------------------------------------------
# Response types
# ---------------------------------------------------------------------------


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict = field(
        default_factory=dict
    )  # {prompt_tokens, completion_tokens, total_tokens}
    latency_ms: float = 0.0
    raw: dict = field(default_factory=dict)  # provider-specific raw response


@dataclass
class CallOpts:
    temperature: float = 0.3
    max_tokens: int = 4096
    stop: list[str] = field(default_factory=list)
    retries: int = 3
    retry_delay_s: float = 2.0


# ---------------------------------------------------------------------------
# Client protocol — any backend implements this
# ---------------------------------------------------------------------------


class LLMClient(Protocol):
    async def call(
        self, system: str, user: str, opts: CallOpts | None = None
    ) -> LLMResponse: ...
    def model_name(self) -> str: ...
    def tier(self) -> str: ...


# ---------------------------------------------------------------------------
# Ollama client — local development
# ---------------------------------------------------------------------------


class OllamaClient:
    def __init__(
        self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def model_name(self) -> str:
        return self.model

    def tier(self) -> str:
        return "light"

    async def call(
        self, system: str, user: str, opts: CallOpts | None = None
    ) -> LLMResponse:
        import httpx

        opts = opts or CallOpts()
        start = time.perf_counter()

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": opts.temperature,
                "num_predict": opts.max_tokens,
            },
        }
        if opts.stop:
            payload["options"]["stop"] = opts.stop

        last_error = None
        for attempt in range(opts.retries):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                latency_ms = (time.perf_counter() - start) * 1000

                return LLMResponse(
                    text=data.get("message", {}).get("content", ""),
                    model=data.get("model", self.model),
                    usage={
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                    },
                    latency_ms=latency_ms,
                    raw=data,
                )
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < opts.retries - 1:
                    await _sleep(opts.retry_delay_s * (2**attempt))

        raise RuntimeError(
            f"Ollama call failed after {opts.retries} attempts: {last_error}"
        )


# ---------------------------------------------------------------------------
# NIM client — NVIDIA NIM (production)
# ---------------------------------------------------------------------------


class NIMClient:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def model_name(self) -> str:
        return self.model

    def tier(self) -> str:
        if "70b" in self.model.lower() or "405b" in self.model.lower():
            return "strong"
        return "light"

    async def call(
        self, system: str, user: str, opts: CallOpts | None = None
    ) -> LLMResponse:
        import httpx

        opts = opts or CallOpts()
        start = time.perf_counter()

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": opts.temperature,
            "max_tokens": opts.max_tokens,
        }
        if opts.stop:
            payload["stop"] = opts.stop

        last_error = None
        for attempt in range(opts.retries):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                latency_ms = (time.perf_counter() - start) * 1000
                choice = data.get("choices", [{}])[0]

                return LLMResponse(
                    text=choice.get("message", {}).get("content", ""),
                    model=data.get("model", self.model),
                    usage=data.get("usage", {}),
                    latency_ms=latency_ms,
                    raw=data,
                )
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < opts.retries - 1:
                    await _sleep(opts.retry_delay_s * (2**attempt))

        raise RuntimeError(
            f"NIM call failed after {opts.retries} attempts: {last_error}"
        )


# ---------------------------------------------------------------------------
# LLM Router — tiered routing by reasoning demand
# Phase 0: single model for all tiers. Split when you have data.
# ---------------------------------------------------------------------------


class LLMRouter:
    def __init__(self, client: LLMClient):
        self._light = client
        self._strong = client
        self._frontier = client

    def light(self) -> LLMClient:
        return self._light

    def strong(self) -> LLMClient:
        return self._strong

    def frontier(self) -> LLMClient:
        return self._frontier

    def configure(
        self,
        light: LLMClient | None = None,
        strong: LLMClient | None = None,
        frontier: LLMClient | None = None,
    ):
        if light:
            self._light = light
        if strong:
            self._strong = strong
        if frontier:
            self._frontier = frontier

    @classmethod
    def from_ollama(
        cls, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"
    ) -> LLMRouter:
        client = OllamaClient(model, base_url)
        return cls(client)

    @classmethod
    def from_nim(
        cls,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
    ) -> LLMRouter:
        client = NIMClient(model, api_key, base_url)
        return cls(client)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _sleep(seconds: float):
    import asyncio

    await asyncio.sleep(seconds)
