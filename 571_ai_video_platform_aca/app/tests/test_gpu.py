"""Live GPU, CPU and RAM utilisation: the VM exporter, GpuMonitor and /api/gpu."""

import importlib.util
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from video_platform.api import create_app
from video_platform.config import Settings
from video_platform.gpu import GpuMonitor
from video_platform.storage import LocalArtifactStore

EXPORTER = Path(__file__).resolve().parents[2] / "infra" / "scripts" / "gpu_stats_exporter.py"
STATS = {"hostname": "vm-comfyui", "timestamp": 1.0, "gpus": [
    {"index": 0, "name": "NVIDIA H100 NVL", "utilization_gpu": 87.0, "utilization_memory": 40.0,
     "memory_used_mib": 61440.0, "memory_total_mib": 95830.0, "temperature_c": 61.0,
     "power_draw_w": 312.5, "power_limit_w": 400.0}],
    "host": {"cpu_percent": 12.5, "cpu_count": 40, "load_1m": 3.2,
             "memory_used_mib": 98304.0, "memory_total_mib": 321536.0}}


def load_exporter():
    spec = importlib.util.spec_from_file_location("gpu_stats_exporter", EXPORTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exporter_parses_nvidia_smi():
    exporter = load_exporter()
    out = ("0, NVIDIA H100 NVL, 87, 40, 61440, 95830, 61, 312.50, 400.00\n"
           "1, NVIDIA A100, Rev 2, [N/A], 3, 1024, 81920, [Not Supported], 70.1, [N/A]\n\n")
    gpus = exporter.parse_nvidia_smi(out)
    assert gpus[0] == STATS["gpus"][0]
    assert gpus[1]["name"] == "NVIDIA A100, Rev 2" and gpus[1]["utilization_gpu"] is None
    assert gpus[1]["memory_used_mib"] == 1024.0 and gpus[1]["temperature_c"] is None
    assert gpus[1]["power_draw_w"] == 70.1 and gpus[1]["power_limit_w"] is None


def test_exporter_parses_host_cpu_and_memory():
    exporter = load_exporter()
    # user nice system idle iowait irq softirq steal guest guest_nice
    prev = exporter.parse_proc_stat("cpu  100 0 50 800 50 0 0 0 10 0\ncpu0 1 2 3 4 5 6 7 8 9 10\nintr 1\n")
    cur = exporter.parse_proc_stat("cpu  250 0 100 1000 50 0 0 0 30 0\n")
    assert prev == (1000, 850) and cur == (1400, 1050)
    assert exporter.cpu_percent(prev, cur) == 50.0
    assert exporter.cpu_percent(cur, cur) is None

    meminfo = "MemTotal:       329252864 kB\nMemFree:        200000000 kB\nMemAvailable:   228589568 kB\nHugePages_Total:       0\n"
    assert exporter.parse_meminfo(meminfo) == (98304.0, 321536.0)
    assert exporter.parse_meminfo("MemTotal: 2048 kB\nMemFree: 512 kB\nBuffers: 256 kB\nCached: 256 kB\n") == (1.0, 2.0)


def test_exporter_read_host_is_best_effort(monkeypatch):
    exporter = load_exporter()
    files = {"/proc/stat": ["cpu  100 0 50 800 50 0 0 0 0 0\n", "cpu  250 0 100 1000 50 0 0 0 0 0\n"],
             "/proc/meminfo": ["MemTotal: 4096 kB\nMemAvailable: 1024 kB\n"],
             "/proc/loadavg": ["0.50 0.40 0.30 1/200 1234\n"]}
    monkeypatch.setattr(exporter, "_read", lambda path: files[path].pop(0) if len(files[path]) > 1 else files[path][0])
    monkeypatch.setattr(exporter.time, "sleep", lambda s: None)
    host = exporter.read_host()
    assert host["cpu_percent"] == 50.0 and host["load_1m"] == 0.5
    assert host["memory_used_mib"] == 3.0 and host["memory_total_mib"] == 4.0

    def unreadable(path):
        raise OSError("no /proc")

    monkeypatch.setattr(exporter, "_read", unreadable)
    assert exporter.read_host() is None


def monitor(handler, urls=("http://vm1:8189", "http://vm2:8189/"), **kw) -> GpuMonitor:
    return GpuMonitor(list(urls), httpx.AsyncClient(transport=httpx.MockTransport(handler)), **kw)


async def test_monitor_reports_online_and_offline_servers():
    def handler(request: httpx.Request):
        assert request.url.path == "/gpu_stats"
        if request.url.host == "vm2":
            raise httpx.ConnectTimeout("timed out")
        return httpx.Response(200, json=STATS)

    snap = await monitor(handler).snapshot()
    assert snap["enabled"] is True
    online, offline = snap["servers"]
    assert online == {"name": "vm-comfyui", "online": True, "error": None, "gpus": STATS["gpus"], "host": STATS["host"]}
    assert offline["name"] == "vm2:8189" and offline["online"] is False and offline["gpus"] == []
    assert offline["host"] is None
    assert "timed out" in offline["error"]


async def test_monitor_accepts_exporters_without_host_stats():
    old = {k: v for k, v in STATS.items() if k != "host"}
    server = (await monitor(lambda request: httpx.Response(200, json=old), urls=["http://vm1:8189"]).snapshot())["servers"][0]
    assert server["online"] is True and server["host"] is None


async def test_monitor_handles_http_errors_and_bad_json():
    def handler(request: httpx.Request):
        if request.url.host == "vm1":
            return httpx.Response(503, json={"error": "nvidia-smi failed"})
        return httpx.Response(200, text="not json")

    servers = (await monitor(handler).snapshot())["servers"]
    assert [s["online"] for s in servers] == [False, False]


async def test_monitor_caches_and_can_be_disabled():
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=STATS)

    m = monitor(handler, urls=["http://vm1:8189"], cache_seconds=60)
    await m.snapshot()
    await m.snapshot()
    assert calls == 1
    m.cache_seconds = 0
    await m.snapshot()
    assert calls == 2

    disabled = await GpuMonitor([]).snapshot()
    assert disabled["enabled"] is False and disabled["servers"] == []


def test_api_gpu(tmp_path):
    settings = Settings(local_output_dir=tmp_path / "out", work_dir=tmp_path / "work", api_key="secret")
    store = LocalArtifactStore(settings.local_output_dir)

    async def close():
        pass

    gpu = monitor(lambda request: httpx.Response(200, json=STATS), urls=["http://vm1:8189"])
    app = create_app(settings, services=(store, lambda manager: None, close), gpu_monitor=gpu)
    with TestClient(app) as client:
        assert client.get("/api/gpu").status_code == 401
        body = client.get("/api/gpu", headers={"X-API-Key": "secret"}).json()
        assert body["enabled"] is True and body["servers"][0]["gpus"][0]["utilization_gpu"] == 87.0
        assert body["servers"][0]["host"]["cpu_percent"] == 12.5

    app = create_app(settings, services=(store, lambda manager: None, close))
    with TestClient(app) as client:
        assert client.get("/api/gpu?key=secret").json()["enabled"] is False
