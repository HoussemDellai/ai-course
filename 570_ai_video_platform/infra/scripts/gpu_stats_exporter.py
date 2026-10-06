#!/usr/bin/env python3
"""Tiny HTTP exporter of the GPU stats reported by nvidia-smi (standard library only).

GET /gpu_stats -> {"hostname": ..., "timestamp": ..., "gpus": [{index, name, utilization_gpu, ...}]}
GET /healthz   -> {"status": "ok"}
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FIELDS = [
    ("index", "index", int),
    ("name", "name", str),
    ("utilization.gpu", "utilization_gpu", float),
    ("utilization.memory", "utilization_memory", float),
    ("memory.used", "memory_used_mib", float),
    ("memory.total", "memory_total_mib", float),
    ("temperature.gpu", "temperature_c", float),
    ("power.draw", "power_draw_w", float),
    ("power.limit", "power_limit_w", float),
]
QUERY = ",".join(f for f, _, _ in FIELDS)
CACHE_SECONDS = 1.0

_lock = threading.Lock()
_cache: tuple[float, dict] | None = None


def _value(raw: str, cast):
    raw = raw.strip()
    if not raw or raw.startswith("[") or raw.upper() == "N/A":  # e.g. [N/A], [Not Supported]
        return None
    try:
        return cast(raw)
    except ValueError:
        return None


def parse_nvidia_smi(output: str) -> list[dict]:
    """Parses `nvidia-smi --query-gpu=<QUERY> --format=csv,noheader,nounits` output."""
    gpus = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) > len(FIELDS):  # a GPU name containing commas
            extra = len(parts) - len(FIELDS)
            parts = [parts[0], ", ".join(parts[1:2 + extra])] + parts[2 + extra:]
        if len(parts) != len(FIELDS):
            continue
        gpus.append({key: _value(raw, cast) for (_, key, cast), raw in zip(FIELDS, parts)})
    return gpus


def read_gpus() -> list[dict]:
    out = subprocess.run(
        ["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    return parse_nvidia_smi(out)


def snapshot() -> dict:
    """Current stats, cached briefly so concurrent callers share one nvidia-smi run."""
    global _cache
    with _lock:
        now = time.time()
        if _cache is None or now - _cache[0] >= CACHE_SECONDS:
            _cache = (now, {"hostname": socket.gethostname(), "timestamp": now, "gpus": read_gpus()})
        return _cache[1]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            self._send(200, {"status": "ok"})
        elif path == "/gpu_stats":
            try:
                self._send(200, snapshot())
            except (OSError, subprocess.SubprocessError) as e:
                self._send(503, {"error": f"nvidia-smi failed: {e}"})
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, format, *args) -> None:  # keep the journal quiet: the app polls every few seconds
        pass


def main() -> None:
    host = os.environ.get("GPU_STATS_HOST", "0.0.0.0")
    port = int(os.environ.get("GPU_STATS_PORT", "8189"))
    print(f"GPU stats exporter listening on {host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
