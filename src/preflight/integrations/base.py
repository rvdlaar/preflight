"""
Preflight Integration Base — abstract foundation for external system connectors.

Every integration inherits from IntegrationClient and implements:
  - health()          — connectivity check
  - fetch()           — retrieve data from the external system
  - push()            — send data to the external system
  - normalize()       — transform external data to Preflight's internal schema

Design decisions:
  - All integrations are async (external calls are I/O-bound)
  - Results are always wrapped in IntegrationResult for consistent error handling
  - Rate limiting and retry logic live at this level, not in callers
  - Each integration owns its own auth (token refresh, credential rotation)
  - Integrations must never block the pipeline — failures degrade gracefully
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx


class IntegrationStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"


@dataclass
class IntegrationResult:
    status: IntegrationStatus
    source: str
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def ok(self) -> bool:
        return self.status in (IntegrationStatus.SUCCESS, IntegrationStatus.PARTIAL)


class IntegrationClient:
    """Base class for all Preflight external integrations."""

    source: str = "base"
    rate_limit_per_second: float = 10.0

    def __init__(self, base_url: str, api_key: str | None = None, tenant: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.tenant = tenant
        self._semaphore = asyncio.Semaphore(int(self.rate_limit_per_second))
        self._last_call: datetime | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def health(self) -> IntegrationResult:
        raise NotImplementedError

    async def fetch(self, query: str, **kwargs: Any) -> IntegrationResult:
        raise NotImplementedError

    async def push(self, data: dict[str, Any], **kwargs: Any) -> IntegrationResult:
        raise NotImplementedError

    def normalize(self, raw: Any) -> dict[str, Any]:
        raise NotImplementedError

    async def _rate_limited(self) -> None:
        """Enforce rate limit: acquire semaphore, then ensure minimum interval between calls."""
        min_interval = 1.0 / max(self.rate_limit_per_second, 0.1)
        async with self._semaphore:
            if self._last_call is not None:
                elapsed = (datetime.now(timezone.utc) - self._last_call).total_seconds()
                if elapsed < min_interval:
                    await asyncio.sleep(min_interval - elapsed)
            self._last_call = datetime.now(timezone.utc)

    def _not_implemented(self, method: str) -> IntegrationResult:
        return IntegrationResult(
            status=IntegrationStatus.UNAVAILABLE,
            source=self.source,
            error=f"{method} not implemented for {self.source}",
        )

    def _get_http_client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        """Return the injected test client or create a fresh one.

        For testing, set ``client._http_client = my_mock_client`` before calling
        any async method. The client will be reused and NOT closed by the caller.
        """
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=timeout)

    @asynccontextmanager
    async def _http_request(self, timeout: float = 30.0):
        """Context manager that yields an httpx.AsyncClient.

        Uses the injected test client if set, otherwise creates a fresh one.
        Only closes the client if we created it (not injected).
        """
        client = self._get_http_client(timeout)
        owned = self._http_client is None
        try:
            yield client
        finally:
            if owned:
                await client.aclose()
