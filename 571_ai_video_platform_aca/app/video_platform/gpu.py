from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

CACHE_SECONDS = 1.5
IDLE_GRACE_SECONDS = 30.0


class ServerActivity:
    """Which GPU servers a job is using right now (or used a moment ago).

    A GPU server that scales to zero when idle must not be woken by telemetry polling, so the monitor only
    queries servers this tracker reports as active."""

    def __init__(self, grace_seconds: float = IDLE_GRACE_SECONDS, clock=time.monotonic):
        self.grace_seconds = grace_seconds
        self._clock = clock
        self._busy: dict[str, int] = {}
        self._last_used: dict[str, float] = {}

    def begin(self, url: str) -> None:
        url = url.rstrip("/")
        self._busy[url] = self._busy.get(url, 0) + 1

    def end(self, url: str) -> None:
        url = url.rstrip("/")
        self._busy[url] = max(0, self._busy.get(url, 0) - 1)
        self._last_used[url] = self._clock()

    def is_active(self, url: str) -> bool:
        url = url.rstrip("/")
        if self._busy.get(url, 0) > 0:
            return True
        last = self._last_used.get(url)
        return last is not None and self._clock() - last < self.grace_seconds


class GpuMonitor:
    """Reads GPU and container resource stats from the ComfyUI telemetry endpoint.

    With an activity tracker, servers no job is using are reported as idle without being contacted."""

    def __init__(self, urls: list[str], http: httpx.AsyncClient | None = None, cache_seconds: float = CACHE_SECONDS,
                 activity: ServerActivity | None = None):
        self.urls = [u.rstrip("/") for u in urls]
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(3.0))
        self.cache_seconds = cache_seconds
        self.activity = activity
        self._lock = asyncio.Lock()
        self._cached: tuple[float, dict[str, Any]] | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.urls)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _server(self, url: str) -> dict[str, Any]:
        name = urlsplit(url).netloc or url
        if self.activity is not None and not self.activity.is_active(url):
            return {"name": name, "online": False, "idle": True, "error": None, "gpus": [], "host": None}
        try:
            r = await self._http.get(f"{url}/gpu_stats")
            r.raise_for_status()
            body = r.json()
            return {"name": body.get("hostname") or name, "online": True, "error": None,
                    "gpus": body.get("gpus", []), "host": body.get("host")}
        except (httpx.HTTPError, ValueError) as e:
            return {"name": name, "online": False, "error": str(e) or type(e).__name__, "gpus": [], "host": None}

    async def snapshot(self) -> dict[str, Any]:
        """Stats of every server, cached briefly so open pages share one request per server."""
        if not self.enabled:
            return {"enabled": False, "timestamp": time.time(), "servers": []}
        async with self._lock:
            now = time.monotonic()
            if self._cached is None or now - self._cached[0] >= self.cache_seconds:
                servers = await asyncio.gather(*(self._server(u) for u in self.urls))
                self._cached = (time.monotonic(), {"enabled": True, "timestamp": time.time(), "servers": servers})
            return self._cached[1]
