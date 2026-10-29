from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from test_gpu import load_exporter

INFRA = Path(__file__).parents[2] / "infra"


def test_comfyui_memory_is_configurable_with_compatible_default():
    app = (INFRA / "aca_comfyui.tf").read_text()
    variables = (INFRA / "variables.tf").read_text()
    memory = variables.split('variable "comfyui_memory_gib" {')[1].split('variable "comfyui_image"')[0]
    assert 'memory  = "${var.comfyui_memory_gib}Gi"' in app
    assert "default     = 4" in memory
    assert "var.comfyui_memory_gib <= 220" in memory
    assert "comfyui_memory_gib" in (INFRA / "education.tfvars").read_text()


def test_comfyui_scales_to_zero_by_default_and_telemetry_follows():
    variables = (INFRA / "variables.tf").read_text()
    replicas = variables.split('variable "comfyui_min_replicas" {')[1].split('variable "comfyui_memory_gib"')[0]
    assert "default     = 0" in replicas
    assert "contains([0, 1], var.comfyui_min_replicas)" in replicas
    app = (INFRA / "container_app.tf").read_text()
    assert 'value = var.comfyui_min_replicas == 0 ? "false" : "true"' in app
    assert 'name  = "GPU_STATS_WHEN_IDLE"' in app
    comfyui = (INFRA / "aca_comfyui.tf").read_text()
    assert 'http_scale_rule {' in comfyui and 'concurrent_requests = "10"' in comfyui


def test_voice_clone_is_right_sized_for_a_t4_that_scales_to_zero():
    variables = (INFRA / "variables.tf").read_text()
    cpu = variables.split('variable "voice_clone_cpu" {')[1].split("}")[0]
    memory = variables.split('variable "voice_clone_memory_gib" {')[1].split("}")[0]
    assert "default     = 2" in cpu and "default     = 16" in memory
    voice = (INFRA / "voice_clone.tf").read_text()
    assert "min_replicas                     = 0" in voice
    assert 'cpu    = var.voice_clone_cpu' in voice and 'memory = "${var.voice_clone_memory_gib}Gi"' in voice


def test_deployment_is_independent_and_gpu_only():
    providers = (INFRA / "providers.tf").read_text()
    variables = (INFRA / "variables.tf").read_text()
    app = (INFRA / "aca_comfyui.tf").read_text()
    environment = (INFRA / "aca_environment.tf").read_text()
    assert 'path = "state-571/terraform.tfstate"' in providers
    assert 'default     = "aivideo571"' in variables
    assert "variable \"vm_" not in variables
    assert "min_replicas                     = var.comfyui_min_replicas" in app
    assert "max_replicas                     = 1" in app
    assert 'revision_mode                = "Single"' in app
    assert "allow_insecure_connections = false" in app
    assert "Consumption-GPU-NC24-A100" in environment
    assert 'memory  = "${var.comfyui_memory_gib}Gi"' in app
    assert 'variable "comfyui_memory_gib" {' in variables
    assert not (INFRA / "vm_comfyui.tf").exists()
    assert 'value = join(",", local.comfyui_urls)' in (INFRA / "container_app.tf").read_text()
    assert "gpu_stats_url = local.comfyui_url" in app
    assert 'for_each                     = local.comfyui_workers' in app
    assert 'to   = azurerm_container_app.comfyui["primary"]' in app
    assert 'name  = "COMFY_WORKER"' in app


def test_downloader_inventory_covers_every_workflow():
    script = (INFRA / "scripts" / "03-download-models.sh").read_text()
    workflows = Path(__file__).parents[1] / "video_platform" / "comfy_workflows"
    for path in workflows.glob("*.json"):
        graph = json.loads(path.read_text())
        for node in graph.values():
            for value in node.get("inputs", {}).values():
                if isinstance(value, str) and value.endswith(".safetensors"):
                    assert value in script, (path.name, value)
    job = (INFRA / "aca_job_download_models.tf").read_text()
    assert "555_comfyui_on_aca" not in job
    assert "raw.githubusercontent.com" not in job
    assert "key_vault_secret_id" in job and "HF_TOKEN" in job
    assert "run-model-job.ps1" in job
    assert "terraform_data.provision_models" in (INFRA / "aca_comfyui.tf").read_text()


def test_cgroup_v2_metrics_use_container_limits(monkeypatch):
    exporter = load_exporter()
    files = {
        "cpu.stat": "usage_usec 2000000\nuser_usec 1000000",
        "cpu.max": "200000 100000",
        "memory.current": str(512 << 20),
        "memory.max": str(2048 << 20),
    }
    monkeypatch.setattr(exporter.os.path, "isfile", lambda _: True)
    monkeypatch.setattr(exporter, "_read", lambda path: files[Path(path).name])
    monkeypatch.setattr(exporter.time, "monotonic", lambda: 10.0)
    assert exporter.read_container()["cpu_percent"] is None
    files["cpu.stat"] = "usage_usec 3000000"
    monkeypatch.setattr(exporter.time, "monotonic", lambda: 11.0)
    result = exporter.read_container()
    assert result["cpu_percent"] == 50.0
    assert result["cpu_count"] == 2
    assert result["memory_used_mib"] == 512
    assert result["memory_total_mib"] == 2048
    assert result["scope"] == "container" and result["load_1m"] is None


def test_cgroup_v1_and_unlimited_metrics(monkeypatch):
    exporter = load_exporter()
    files = {"cpu.cfs_quota_us": "-1", "cpu.cfs_period_us": "100000",
             "cpuacct.usage": "1000000", "memory.usage_in_bytes": "1048576",
             "memory.limit_in_bytes": str(1 << 62)}
    monkeypatch.setattr(exporter.os.path, "isfile", lambda _: False)
    monkeypatch.setattr(exporter, "_read", lambda path: files[Path(path).name])
    result = exporter.read_container()
    assert result["cpu_count"] is None and result["memory_total_mib"] is None
    assert result["memory_used_mib"] == 1


def test_unavailable_container_metrics_are_explicit(monkeypatch, caplog):
    exporter = load_exporter()
    def fail():
        raise OSError("no cgroup access")
    monkeypatch.setattr(exporter, "_container_values", fail)
    result = exporter.read_container()
    assert result["error"] == "no cgroup access"
    assert result["cpu_percent"] is None and result["memory_total_mib"] is None
    assert "unavailable" in caplog.text


async def test_comfyui_telemetry_route_is_nonblocking_and_reports_errors(monkeypatch):
    from aiohttp import web

    routes = web.RouteTableDef()
    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(instance=types.SimpleNamespace(routes=routes))
    monkeypatch.setitem(sys.modules, "server", server)
    package = types.ModuleType("platform_gpu")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "platform_gpu", package)
    monkeypatch.setitem(sys.modules, "platform_gpu.gpu_stats_exporter", load_exporter())
    spec = importlib.util.spec_from_file_location("platform_gpu.extension", INFRA / "scripts" / "comfyui_gpu_extension.py")
    extension = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extension)
    assert next(iter(routes)).path == "/gpu_stats"
    calls = []
    async def thread_call(callback):
        calls.append(callback)
        return {"gpus": [], "host": None}
    monkeypatch.setattr(asyncio, "to_thread", thread_call)
    response = await extension.gpu_stats(None)
    assert response.status == 200 and calls == [extension.snapshot]
    assert response.headers["Cache-Control"] == "no-store"
    async def fail(callback):
        raise OSError("CUDA unavailable")
    monkeypatch.setattr(asyncio, "to_thread", fail)
    response = await extension.gpu_stats(None)
    assert response.status == 503 and b"CUDA unavailable" in response.body


def test_fish_runs_in_its_own_a100_app_that_scales_to_zero():
    a100 = (INFRA / "voice_clone_a100.tf").read_text()
    assert 'workload_profile_name        = "GPU-NC24-A100"' in a100
    assert "min_replicas                     = 0" in a100
    assert "http_scale_rule {" in a100
    assert "external_enabled           = false" in a100
    assert "image  = local.voice_clone_image" in a100 and 'value = "0"' in a100  # same image, bf16 (no --half)
    assert "random_password.voice_clone_key[0].result" in a100
    variables = (INFRA / "variables.tf").read_text()
    assert variables.split('variable "voice_clone_a100_enabled" {')[1].split("}")[0].count("default     = true") == 1
    orchestrator = (INFRA / "container_app.tf").read_text()
    assert 'name  = "VOICE_CLONE_A100_URL"' in orchestrator
    assert "voice_clone_a100_url" in (INFRA / "outputs.tf").read_text()
