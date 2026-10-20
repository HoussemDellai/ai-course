import asyncio
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import aiohttp
from aiohttp import web
from starlette.testclient import TestClient

from gateway import OFFICIAL_TOOLS, create_app, proxy_app, public_urls, validate_settings

TOKEN = "test-only-" + "a" * 40
FIXTURE = {
    "DemoBackendNode": {
        "input": {"required": {"text": ["STRING", {"default": ""}]}},
        "output": ["STRING"],
        "output_name": ["text"],
        "name": "DemoBackendNode",
        "display_name": "DemoBackendNode",
        "description": "Marker from the actual test backend",
        "python_module": "nodes",
        "category": "testing",
        "output_node": False,
    },
}


class Backend(BaseHTTPRequestHandler):
    paths = []

    def do_GET(self):
        self.paths.append(self.path)
        if self.path == "/object_info":
            body = json.dumps(FIXTURE).encode()
            self.send_response(200)
        else:
            body = b'{"error":"not found"}'
            self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        cls.thread = threading.Thread(target=cls.backend.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.backend.server_port}"
        cls.env = patch.dict(os.environ, {
            "MCP_TOKEN": TOKEN, "COMFY_BACKEND_URL": cls.url,
            "COMFY_BIN": str(Path(sys.executable).with_name("comfy.exe" if os.name == "nt" else "comfy")),
        })
        cls.env.start()
        cls.client = TestClient(create_app())
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.env.stop()
        cls.backend.shutdown()
        cls.backend.server_close()
        cls.thread.join()

    def rpc(self, method, params=None):
        return self.client.post("/mcp", headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json, text/event-stream",
        }, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})

    def test_health_does_not_require_token(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)

    def test_missing_and_wrong_tokens_rejected(self):
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            response = self.client.post("/mcp", headers=headers, json={})
            self.assertEqual(response.status_code, 401)
            self.assertNotIn(TOKEN, response.text)

    def test_initialize(self):
        response = self.rpc("initialize", {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertEqual(result["serverInfo"]["name"], "comfy-mcp")
        self.assertIn("tools", result["capabilities"])

    def test_only_remote_safe_tools_exposed(self):
        response = self.rpc("tools/list")
        self.assertEqual(response.status_code, 200, response.text)
        names = {tool["name"] for tool in response.json()["result"]["tools"]}
        self.assertEqual(names, OFFICIAL_TOOLS | {"run_workflow", "fetch_outputs"})

    def test_official_nodes_tool_reaches_backend(self):
        response = self.rpc("tools/call", {
            "name": "nodes", "arguments": {"action": "get", "name": "DemoBackendNode"},
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertFalse(result.get("isError"), result)
        self.assertIn("DemoBackendNode", json.dumps(result))
        self.assertIn("/object_info", Backend.paths)

    def test_backend_http_error_preserved(self):
        import httpx
        response = httpx.get("http://127.0.0.1:8188/not-found")
        self.assertEqual(response.status_code, 404)

    def test_local_install_tool_cannot_be_called(self):
        response = self.rpc("tools/call", {
            "name": "install_node", "arguments": {"names": ["anything"]},
        })
        result = response.json()
        self.assertTrue("error" in result or result["result"].get("isError"), result)

    def test_bad_settings_fail_closed(self):
        for backend in ("", "ftp://example.org", "https://user:pass@example.org", "http://127.0.0.1:8188"):
            with self.assertRaises(ValueError):
                validate_settings(TOKEN, backend)
        with self.assertRaises(ValueError):
            validate_settings("short", self.url)

    def test_output_urls_are_external(self):
        self.assertEqual(
            public_urls({"urls": ["http://127.0.0.1:8188/view?filename=test.png"]}, self.url),
            {"urls": [self.url + "/view?filename=test.png"]},
        )

    def test_official_tool_errors_remain_actionable(self):
        response = self.rpc("tools/call", {
            "name": "nodes", "arguments": {"action": "not-an-action"},
        })
        result = response.json()["result"]
        self.assertTrue(result.get("isError"), result)
        self.assertIn("invalid nodes action", json.dumps(result))


class ProxyTests(unittest.IsolatedAsyncioTestCase):
    async def test_websocket_and_query_forwarding(self):
        upstream = web.Application()

        async def echo(request):
            self.assertEqual(request.query["clientId"], "test-client")
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            async for message in socket:
                await socket.send_str("backend:" + message.data)
            return socket

        upstream.router.add_get("/ws", echo)
        upstream_runner = web.AppRunner(upstream)
        await upstream_runner.setup()
        upstream_site = web.TCPSite(upstream_runner, "127.0.0.1", 0)
        await upstream_site.start()
        port = upstream_site._server.sockets[0].getsockname()[1]
        relay = web.AppRunner(proxy_app(f"http://127.0.0.1:{port}"))
        await relay.setup()
        relay_site = web.TCPSite(relay, "127.0.0.1", 0)
        await relay_site.start()
        relay_port = relay_site._server.sockets[0].getsockname()[1]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(f"http://127.0.0.1:{relay_port}/ws?clientId=test-client") as socket:
                    await socket.send_str("hello")
                    message = await asyncio.wait_for(socket.receive(), 5)
                    self.assertEqual(message.data, "backend:hello")
        finally:
            await relay.cleanup()
            await upstream_runner.cleanup()

    async def test_unavailable_backend_is_explicit_502(self):
        runner = web.AppRunner(proxy_app("http://127.0.0.1:1"))
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with aiohttp.ClientSession() as session:
                with self.assertLogs("comfy-mcp-aca", level="ERROR"):
                    async with session.get(f"http://127.0.0.1:{port}/object_info") as response:
                        self.assertEqual(response.status, 502)
        finally:
            await runner.cleanup()


if __name__ == "__main__":
    unittest.main()
