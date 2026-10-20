"""Read-only remote MCP verification. Never submits workflows or downloads models."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx


def verify(endpoint: str, token: str) -> dict:
    if not endpoint.startswith("https://") or not endpoint.endswith("/mcp"):
        raise ValueError("Supply the HTTPS MCP endpoint ending in /mcp")
    if len(token) < 32:
        raise ValueError("Supply MCP_TOKEN; do not put the token on the command line")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
    }
    with httpx.Client(timeout=180) as client:
        for auth in (None, "Bearer incorrect-token"):
            response = client.post(
                endpoint, headers={"Authorization": auth} if auth else {},
                json={"jsonrpc": "2.0", "id": 0, "method": "tools/list"},
            )
            if response.status_code != 401:
                raise RuntimeError(f"Authentication check expected 401, got {response.status_code}")

        def rpc(method: str, params: dict) -> dict:
            response = client.post(endpoint, headers=headers, json={
                "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
            })
            response.raise_for_status()
            body = response.json()
            if "error" in body or "result" not in body:
                raise RuntimeError(f"MCP {method} failed: {body}")
            result = body["result"]
            if result.get("isError"):
                raise RuntimeError(f"MCP tool failed: {result}")
            return result

        initialized = rpc("initialize", {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "aca-readonly-verifier", "version": "1.0"},
        })
        tools = rpc("tools/list", {})
        names = sorted(tool["name"] for tool in tools["tools"])
        if "nodes" not in names or "install_node" in names:
            raise RuntimeError(f"Unexpected tool surface: {names}")
        nodes = rpc("tools/call", {
            "name": "nodes", "arguments": {"action": "get", "name": "KSampler"},
        })
        if "KSampler" not in json.dumps(nodes):
            raise RuntimeError("Node discovery did not identify the actual KSampler node")
        models = rpc("tools/call", {"name": "search_models", "arguments": {}})
        return {
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "authentication": "missing and incorrect tokens rejected; valid token accepted",
            "server": initialized["serverInfo"],
            "tools": names,
            "backend_node": nodes,
            "model_inventory": models,
            "generation_submitted": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.endpoint, os.environ.get("MCP_TOKEN", ""))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PASS: authenticated MCP and read-only backend discovery. Report: {args.report}")


if __name__ == "__main__":
    main()
