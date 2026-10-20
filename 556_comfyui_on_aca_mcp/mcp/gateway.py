"""Anonymous HTTP hosting for the official Comfy MCP demo tool registry."""

import asyncio
import contextlib
import functools
import json
import logging
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.responses import PlainTextResponse
from starlette.routing import Route

LOG = logging.getLogger("comfy-mcp-aca")
SESSION = web.AppKey("session", aiohttp.ClientSession)
LOCAL_URL = "http://127.0.0.1:8188"
OFFICIAL_TOOLS = frozenset({
    "nodes", "search_models", "system_stats", "search_templates",
    "get_template", "run_template", "generate_image", "job",
})
HOP_HEADERS = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "host", "authorization",
})


def validate_settings(backend: str) -> None:
    parsed = urlsplit(backend)
    if (
        parsed.scheme not in ("http", "https") or not parsed.hostname
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("COMFY_BACKEND_URL must be an HTTP(S) origin without credentials")
    if parsed.hostname in ("localhost", "127.0.0.1", "::1") and parsed.port == 8188:
        raise ValueError("COMFY_BACKEND_URL must not point back at the forwarding listener")


async def relay_websocket(source, destination) -> None:
    async for message in source:
        if message.type == aiohttp.WSMsgType.TEXT:
            await destination.send_str(message.data)
        elif message.type == aiohttp.WSMsgType.BINARY:
            await destination.send_bytes(message.data)
        elif message.type == aiohttp.WSMsgType.ERROR:
            raise RuntimeError("ComfyUI WebSocket relay failed") from source.exception()


def proxy_app(backend: str) -> web.Application:
    app = web.Application(client_max_size=32 * 1024 * 1024)

    async def session_lifetime(application) -> AsyncIterator[None]:
        async with aiohttp.ClientSession(
            auto_decompress=False,
            timeout=aiohttp.ClientTimeout(total=180, connect=15),
        ) as session:
            application[SESSION] = session
            yield

    async def forward(request: web.Request) -> web.StreamResponse:
        session = request.app[SESSION]
        url = backend.rstrip("/") + request.raw_path
        try:
            if request.headers.get("Upgrade", "").lower() == "websocket":
                async with session.ws_connect(url, heartbeat=30) as upstream:
                    downstream = web.WebSocketResponse(heartbeat=30)
                    await downstream.prepare(request)
                    tasks = {
                        asyncio.create_task(relay_websocket(upstream, downstream)),
                        asyncio.create_task(relay_websocket(downstream, upstream)),
                    }
                    try:
                        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                        for task in done:
                            task.result()
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        await downstream.close()
                    return downstream
            headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
            async with session.request(
                request.method, url, data=await request.read(),
                headers=headers, allow_redirects=False,
            ) as upstream:
                response = web.StreamResponse(
                    status=upstream.status,
                    headers={k: v for k, v in upstream.headers.items() if k.lower() not in HOP_HEADERS},
                )
                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(64 * 1024):
                    await response.write(chunk)
                await response.write_eof()
                return response
        except (aiohttp.ClientError, TimeoutError):
            LOG.exception("ComfyUI backend forwarding failed")
            raise web.HTTPBadGateway(text="ComfyUI backend unavailable; check GPU startup and logs")

    app.cleanup_ctx.append(session_lifetime)
    app.router.add_route("*", "/{path:.*}", forward)
    return app


def public_urls(value: Any, backend: str) -> Any:
    if isinstance(value, str):
        return value.replace(LOCAL_URL, backend)
    if isinstance(value, list):
        return [public_urls(item, backend) for item in value]
    if isinstance(value, dict):
        return {key: public_urls(item, backend) for key, item in value.items()}
    return value


def actionable_tool(function):
    from comfy_mcp.errors import ComfyCliError

    if asyncio.iscoroutinefunction(function):
        @functools.wraps(function)
        async def asynchronous(*args, **kwargs):
            try:
                return await function(*args, **kwargs)
            except ComfyCliError as exc:
                LOG.warning("ComfyUI tool %s failed: %s", function.__name__, exc)
                raise ToolError(str(exc)) from exc
        return asynchronous

    @functools.wraps(function)
    def synchronous(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ComfyCliError as exc:
            LOG.warning("ComfyUI tool %s failed: %s", function.__name__, exc)
            raise ToolError(str(exc)) from exc
    return synchronous


def create_app():
    backend = os.environ.get("COMFY_BACKEND_URL", "").rstrip("/")
    validate_settings(backend)
    os.environ["COMFY_LOCAL_URL"] = LOCAL_URL
    os.environ["COMFYUI_URL"] = LOCAL_URL
    os.environ["COMFY_CLI_NO_REMOTE_REFRESH"] = "1"
    os.environ["COMFY_CLI_TELEMETRY_ENABLED"] = "false"

    from comfy_mcp import server as official

    mcp = MCPServer("comfy-mcp", version="0.10.0-aca", instructions=(
        "Drive the ACA ComfyUI GPU backend, not this CPU gateway. No models are "
        "provisioned initially: inspect nodes and model inventory before running "
        "workflows. Never install or launch software locally. Outputs on the GPU "
        "replica are ephemeral; retrieve them before it scales down."
    ))
    for name in sorted(OFFICIAL_TOOLS):
        mcp.add_tool(actionable_tool(getattr(official, name)))

    async def run_workflow(
        workflow: dict[str, Any], wait: bool = False, timeout_seconds: float = 110,
    ) -> Any:
        """Submit an API-format workflow object to the GPU backend; incurs GPU charges."""
        with tempfile.TemporaryDirectory(prefix="comfy-workflow-") as directory:
            path = Path(directory) / "workflow.json"
            path.write_text(json.dumps(workflow), encoding="utf-8")
            return await official.run_workflow(
                str(path), wait=wait, timeout_seconds=timeout_seconds, confirm_spend=False,
            )

    async def fetch_outputs(prompt_id: str) -> Any:
        """Return public GPU-backend output URLs without writing arbitrary gateway files."""
        result = await asyncio.to_thread(
            official.fetch_outputs, prompt_id, tempfile.gettempdir(), url_only=True,
        )
        return public_urls(result, backend)

    app = mcp.streamable_http_app(
        host="0.0.0.0", stateless_http=True, json_response=True,
        max_request_body_size=4 * 1024 * 1024,
    )
    original_lifespan = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(application):
        runner = web.AppRunner(proxy_app(backend), access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, "127.0.0.1", 8188).start()
            async with original_lifespan(application):
                LOG.info("Official Comfy MCP ready; backend=%s", backend)
                yield
        finally:
            await runner.cleanup()

    mcp.add_tool(actionable_tool(run_workflow))
    mcp.add_tool(actionable_tool(fetch_outputs))
    app.router.lifespan_context = lifespan
    app.routes.insert(0, Route("/healthz", lambda request: PlainTextResponse("ok")))
    return app
