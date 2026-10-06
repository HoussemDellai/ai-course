#!/usr/bin/env python3
"""Tiny HTTP exporter of the GPU stats reported by nvidia-smi, plus host CPU and RAM (standard library only).

GET /gpu_stats -> {"hostname": ..., "timestamp": ..., "gpus": [{index, name, utilization_gpu, ...}],
                   "host": {cpu_percent, cpu_count, load_1m, memory_used_mib, memory_total_mib} | null}
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
CPU_SAMPLE_SECONDS = 0.2

_lock = threading.Lock()
_cache: tuple[float, dict] | None = None
_cpu_prev: tuple[int, int] | None = None  # (total, idle) jiffies of the previous /proc/stat read


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


def parse_proc_stat(text: str) -> tuple[int, int]:
    """(total, idle) jiffies of the aggregate `cpu` line of /proc/stat; iowait counts as idle."""
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0] == "cpu":
            values = [int(v) for v in parts[1:]]
            # guest and guest_nice (9th/10th) are already included in user and nice.
            total = sum(values[:8])
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            return total, idle
    raise ValueError("no cpu line in /proc/stat")


def cpu_percent(prev: tuple[int, int], cur: tuple[int, int]) -> float | None:
    total, idle = cur[0] - prev[0], cur[1] - prev[1]
    if total <= 0:
        return None
    return round(max(0.0, min(100.0, 100.0 * (total - idle) / total)), 1)


def parse_meminfo(text: str) -> tuple[float, float]:
    """(used, total) MiB from /proc/meminfo; used = MemTotal - MemAvailable."""
    kib = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        fields = rest.split()
        if fields:
            try:
                kib[key.strip()] = int(fields[0])
            except ValueError:
                pass
    total = kib["MemTotal"]
    available = kib.get("MemAvailable", kib.get("MemFree", 0) + kib.get("Buffers", 0) + kib.get("Cached", 0))
    return round((total - available) / 1024, 1), round(total / 1024, 1)


def _read(path: str) -> str:
    with open(path, encoding="ascii") as f:
        return f.read()


def read_host() -> dict | None:
    """CPU and RAM of the VM. None if /proc can't be read: the GPU stats are still served."""
    global _cpu_prev
    try:
        cur = parse_proc_stat(_read("/proc/stat"))
        if _cpu_prev is None:  # first call: no previous sample to diff against
            _cpu_prev = cur
            time.sleep(CPU_SAMPLE_SECONDS)
            cur = parse_proc_stat(_read("/proc/stat"))
        cpu = cpu_percent(_cpu_prev, cur)
        _cpu_prev = cur
        used, total = parse_meminfo(_read("/proc/meminfo"))
        try:
            load_1m = float(_read("/proc/loadavg").split()[0])
        except (OSError, ValueError, IndexError):
            load_1m = None
        return {"cpu_percent": cpu, "cpu_count": os.cpu_count(), "load_1m": load_1m,
                "memory_used_mib": used, "memory_total_mib": total}
    except (OSError, ValueError, KeyError, IndexError):
        return None


def snapshot() -> dict:
    """Current stats, cached briefly so concurrent callers share one nvidia-smi run."""
    global _cache
    with _lock:
        now = time.time()
        if _cache is None or now - _cache[0] >= CACHE_SECONDS:
            gpus = read_gpus()
            _cache = (now, {"hostname": socket.gethostname(), "timestamp": now, "gpus": gpus, "host": read_host()})
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
