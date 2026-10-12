from __future__ import annotations

import asyncio
import logging
import subprocess

from aiohttp import web
from server import PromptServer

from .gpu_stats_exporter import snapshot

log = logging.getLogger(__name__)
NODE_CLASS_MAPPINGS = {}


@PromptServer.instance.routes.get("/gpu_stats")
async def gpu_stats(request: web.Request) -> web.Response:
    try:
        body = await asyncio.to_thread(snapshot)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        log.error("GPU telemetry failed: %s", e)
        return web.json_response({"error": f"GPU telemetry failed: {e}"}, status=503)
    return web.json_response(body, headers={"Cache-Control": "no-store"})
