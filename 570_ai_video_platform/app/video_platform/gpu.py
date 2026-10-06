from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

CACHE_SECONDS = 1.5


class GpuMonitor:
    """Reads live GPU stats from the exporters on the GPU VMs (infra/scripts/gpu_stats_exporter.py)."""

    def __init__(self, urls: list[str], http: httpx.AsyncClient | None = None, cache_seconds: float = CACHE_SECONDS):
        self.urls = [u.rstrip("/") for u in urls]
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(3.0))
        self.cache_seconds = cache_seconds
        self._lock = asyncio.Lock()
        self._cached: tuple[float, dict[str, Any]] | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.urls)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _server(self, url: str) -> dict[str, Any]:
        name = urlsplit(url).netloc or url
        try:
            r = await self._http.get(f"{url}/gpu_stats")
            r.raise_for_status()
            body = r.json()
            return {"name": body.get("hostname") or name, "online": True, "error": None,
                    "gpus": body.get("gpus", [])}
        except (httpx.HTTPError, ValueError) as e:
            return {"name": name, "online": False, "error": str(e) or type(e).__name__, "gpus": []}

    async def snapshot(self) -> dict[str, Any]:
        """Stats of every server, cached briefly so many open pages share one request per VM."""
        if not self.enabled:
            return {"enabled": False, "timestamp": time.time(), "servers": []}
        async with self._lock:
            now = time.monotonic()
            if self._cached is None or now - self._cached[0] >= self.cache_seconds:
                servers = await asyncio.gather(*(self._server(u) for u in self.urls))
                self._cached = (time.monotonic(), {"enabled": True, "timestamp": time.time(), "servers": servers})
            return self._cached[1]
