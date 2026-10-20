from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_aca import INFRA
from test_model_downloads import BASH

SCRIPTS = INFRA / "scripts"
COMMIT = "b0b743566f65daafc423b4fea8a2fbda94b3384a"
PWSH = shutil.which("pwsh")


def bash_path(path: Path) -> str:
    value = path.as_posix()
    return f"/{value[0].lower()}{value[2:]}" if os.name == "nt" else value


@pytest.fixture
def runtime(tmp_path):
    if not BASH:
        pytest.skip("Bash required for bootstrap checks")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    comfy = tmp_path / "comfy"
    calls = tmp_path / "calls"
    git = bin_dir / "git"
    git.write_text("""#!/bin/bash
set -eu
echo "$*" >> "$CALLS"
if [[ "$1" == config ]]; then
  [[ "$*" == "config --global --add safe.directory $COMFY_DIR" ]] || exit 99
  [[ "${GIT_CONFIG_FAIL:-0}" == 0 ]] || exit 8
  : > "$CALLS.safe"
  exit 0
fi
if [[ "${REQUIRE_SAFE_DIRECTORY:-0}" == 1 && ! -f "$CALLS.safe" ]]; then
  echo "fatal: detected dubious ownership" >&2
  exit 128
fi
dir=$2; shift 2
case "$1" in
  init) mkdir -p "$dir/.git" ;;
  remote) ;;
  fetch) [[ "${FETCH_FAIL:-0}" == 0 ]] || exit 5 ;;
  rev-parse)
    if [[ "$*" == *--verify* && ! -f "$dir/main.py" ]]; then exit 1; fi
    echo "${ACTUAL_COMMIT:-b0b743566f65daafc423b4fea8a2fbda94b3384a}" ;;
  checkout) printf 'print("ready")' > "$dir/main.py"; : > "$dir/requirements.txt" ;;
  *) exit 99 ;;
esac
""", encoding="utf-8")
    python = bin_dir / "python3"
    python.write_text("""#!/bin/bash
set -eu
echo "python $*" >> "$CALLS"
[[ "${PYTHON_FAIL:-0}" == 0 ]] || exit 7
""", encoding="utf-8")
    git.chmod(0o755)
    python.chmod(0o755)
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("torch==2.11.0\n")
    env = {**os.environ, "COMFY_DIR": bash_path(comfy), "CALLS": bash_path(calls),
           "COMFY_CONSTRAINTS": bash_path(constraints), "PROVISION_VERSION": "revision1",
           "COMFY_BOOTSTRAP_PATH": bash_path(tmp_path / "bootstrap.sh"),
           "COMFY_BOOTSTRAP_B64": base64.b64encode((SCRIPTS / "02-install-comfyui.sh").read_bytes()).decode()}
    def run(name, **variables):
        source = f'export PATH="{bash_path(bin_dir)}:$PATH"\n' + (SCRIPTS / name).read_text()
        source = source.replace("/tmp/", f"{bash_path(tmp_path)}/")
        return subprocess.run([BASH, "-s"], input=source, text=True, capture_output=True,
                              env={**env, **variables}, timeout=30)
    return run, comfy, calls


def test_bootstrap_first_start_and_restart(runtime):
    run, comfy, calls = runtime
    first = run("02-install-comfyui.sh")
    assert first.returncode == 0, first.stderr
    assert (comfy / "main.py").is_file()
    before = calls.read_text().count("fetch")
    second = run("02-install-comfyui.sh")
    assert second.returncode == 0, second.stderr
    assert calls.read_text().count("fetch") == before


def test_bootstrap_recovers_interrupted_initial_fetch(runtime):
    run, comfy, _ = runtime
    failed = run("02-install-comfyui.sh", FETCH_FAIL="1")
    assert failed.returncode != 0
    assert (comfy / ".git").exists() and not (comfy / "main.py").exists()
    recovered = run("02-install-comfyui.sh")
    assert recovered.returncode == 0, recovered.stderr


def test_bootstrap_rejects_changed_release(runtime):
    run, comfy, _ = runtime
    result = run("02-install-comfyui.sh", ACTUAL_COMMIT="bad")
    assert result.returncode != 0 and "release checksum changed" in result.stderr
    assert not (comfy / "main.py").exists()


def test_startup_requires_provisioning_and_preserves_pytorch(runtime):
    run, comfy, calls = runtime
    result = run("start-comfyui.sh")
    assert result.returncode != 0 and "not completed" in result.stderr
    assert run("02-install-comfyui.sh").returncode == 0
    marker = comfy / ".platform-models-ready"
    marker.write_text("stale")
    result = run("start-comfyui.sh")
    assert result.returncode != 0 and "this revision" in result.stderr
    marker.write_text("revision1")
    for name in ("input", "output", "user"):
        (comfy / name).mkdir()
    result = run("start-comfyui.sh", REQUIRE_SAFE_DIRECTORY="1")
    assert result.returncode == 0, result.stderr
    commands = calls.read_text()
    startup_commands = commands[commands.index("config --global --add safe.directory"):]
    assert startup_commands.splitlines()[0] == f"config --global --add safe.directory {bash_path(comfy)}"
    assert "rev-parse" in startup_commands
    assert "--constraint" in commands
    assert "python main.py --listen 0.0.0.0 --port 8188 --disable-xformers" in commands
    assert f"--input-directory {bash_path(comfy / 'input')}" in commands
    assert f"--user-directory {bash_path(comfy / 'user')}" in commands
    failed = run("start-comfyui.sh", PYTHON_FAIL="1")
    assert failed.returncode != 0


def test_startup_stops_when_git_trust_configuration_fails(runtime):
    run, comfy, calls = runtime
    assert run("02-install-comfyui.sh").returncode == 0
    (comfy / ".platform-models-ready").write_text("revision1")
    calls.write_text("")
    result = run("start-comfyui.sh", GIT_CONFIG_FAIL="1")
    assert result.returncode == 8
    assert calls.read_text().splitlines() == [
        f"config --global --add safe.directory {bash_path(comfy)}",
    ]

@pytest.mark.parametrize("worker", ["primary", "secondary", "invalid"])
def test_worker_runtime_directories_are_isolated(runtime, worker):
    run, comfy, calls = runtime
    assert run("02-install-comfyui.sh").returncode == 0
    (comfy / ".platform-models-ready").write_text("revision1")
    media_dir = comfy if worker == "primary" else comfy / "workers" / "secondary"
    for name in ("input", "output", "user"):
        (media_dir / name).mkdir(parents=True, exist_ok=True)
    result = run("start-comfyui.sh", COMFY_WORKER=worker)
    if worker == "invalid":
        assert result.returncode != 0 and "COMFY_WORKER" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        commands = calls.read_text()
        for name in ("input", "output", "user"):
            assert f"--{name}-directory {bash_path(media_dir / name)}" in commands
        assert f"comfyui-{worker}" in commands


def test_worker_startup_rejects_missing_media_directories(runtime):
    run, comfy, _ = runtime
    assert run("02-install-comfyui.sh").returncode == 0
    (comfy / ".platform-models-ready").write_text("revision1")
    result = run("start-comfyui.sh", COMFY_WORKER="secondary")
    assert result.returncode != 0 and "worker directory is missing or inaccessible" in result.stderr


@pytest.mark.parametrize("chown_fail", ["0", "1", "secondary"])
def test_provisioning_sets_scoped_runtime_ownership_before_ready_marker(runtime, tmp_path, chown_fail):
    run, comfy, calls = runtime
    bin_dir = tmp_path / "bin"
    for name in ("apt-get", "flock", "chown"):
        tool = bin_dir / name
        tool.write_text(f"""#!/bin/bash
set -eu
echo "{name} $*" >> "$CALLS"
if [[ "{name}" == chown ]]; then
  if [[ "${{CHOWN_FAIL:-0}}" == 1 ]]; then exit 9; fi
  if [[ "${{CHOWN_FAIL:-0}}" == secondary && "$*" == *workers/secondary* ]]; then exit 9; fi
fi
""", encoding="utf-8")
        tool.chmod(0o755)
    downloader = '[[ -d "$MODEL_DIR" ]] || mkdir -p "$MODEL_DIR"\necho download >> "$CALLS"\n'
    result = run("provision-models.sh", CHOWN_FAIL=chown_fail,
                 GPU_EXPORTER_B64=base64.b64encode(b"exporter").decode(),
                 GPU_EXTENSION_B64=base64.b64encode(b"extension").decode(),
                 MODEL_DOWNLOADER_B64=base64.b64encode(downloader.encode()).decode())
    assert (result.returncode == 0) is (chown_fail == "0"), result.stderr
    commands = calls.read_text().splitlines()
    ownership = next(line for line in commands if line.startswith("chown "))
    assert ownership == "chown 10000:10000 " + " ".join(
        bash_path(comfy / name) for name in ("input", "output", "temp")
    )
    assert all((comfy / name).is_dir() for name in ("input", "output", "temp"))
    marker = comfy / ".platform-models-ready"
    if chown_fail == "0":
        assert all((comfy / "workers" / "secondary" / name).is_dir() for name in ("input", "output", "user"))
        assert any(line.startswith("chown 10000:10000 ") and "/workers/secondary/output" in line
                   for line in commands)
        assert marker.read_text().strip() == "revision1"
        assert commands.index(ownership) < commands.index("download")
    else:
        assert not marker.exists()
        assert "download" not in commands


def run_ps(script, tmp_path, prelude="", env=None, args=None):
    if not PWSH:
        pytest.skip("PowerShell required for deployment helper checks")
    wrapper = tmp_path / "wrapper.ps1"
    wrapper.write_text(prelude + f"\n& '{script}' " + (args or ""), encoding="utf-8")
    return subprocess.run([PWSH, "-NoProfile", "-File", str(wrapper)], capture_output=True,
                          text=True, encoding="utf-8", env={**os.environ, **(env or {})}, timeout=30)

@pytest.mark.parametrize("windows,exit_code", [(True, 0), (True, 9), (False, 0), (False, 9)])
def test_acr_build_uses_utf8_and_preserves_failure(tmp_path, windows, exit_code):
    install = tmp_path / "Azure CLI"
    launcher = install / "wbin" / ("az.cmd" if windows else "az")
    launcher.parent.mkdir(parents=True)
    launcher.touch()
    python = install / "python.exe"
    python.touch()
    prelude = """
function global:Get-Command {
    return @([pscustomobject]@{Source=$env:TEST_AZ}, [pscustomobject]@{Source="unusable-second-launcher"})
}
function global:FakeCli {
    $prefix = if ($env:TEST_WINDOWS -eq "1") { @("-I","-B","-X","utf8","-m","azure.cli") } else { @() }
    $expected = $prefix + @("acr","build","--subscription","test-sub","--registry","test-acr",
        "--image","video-platform:test","--file","drawio_runtime/Dockerfile.education",".")
    if (($args -join "|") -ne ($expected -join "|")) { throw "Unexpected CLI arguments: $args" }
    if ($env:PYTHONUTF8 -ne "1" -or $env:PYTHONIOENCODING -ne "utf-8") { throw "Missing UTF-8 environment" }
    [Console]::Out.WriteLine([char]0x2500 + [string][char]0x2713)
    $global:LASTEXITCODE = [int]$env:TEST_EXIT_CODE
}
Set-Variable -Name IsWindows -Value ($env:TEST_WINDOWS -eq "1") -Force -Scope Global
$target = if ($env:TEST_WINDOWS -eq "1") { $env:TEST_PYTHON } else { $env:TEST_AZ }
Set-Item "Function:global:$target" ${function:FakeCli}
"""
    result = run_ps(SCRIPTS / "build-app-image.ps1", tmp_path, prelude, env={
        "TEST_AZ": str(launcher), "TEST_PYTHON": str(python), "TEST_WINDOWS": "1" if windows else "0",
        "TEST_EXIT_CODE": str(exit_code), "SUBSCRIPTION_ID": "test-sub", "ACR_NAME": "test-acr",
        "APP_IMAGE_TAG": "video-platform:test", "APP_DOCKERFILE": "drawio_runtime/Dockerfile.education",
    })
    assert (result.returncode == 0) is (exit_code == 0), result.stdout + result.stderr
    assert "\u2500\u2713" in result.stdout
    if exit_code:
        assert "ACR image build failed with exit code 9" in result.stderr


@pytest.mark.parametrize("status,success", [("Succeeded", True), ("Failed", False), ("Stopped", False),
                                         ("Unexpected", False), ("Running", False)])
def test_model_job_checks_execution_result(tmp_path, status, success):
    prelude = """
function global:az {
  $global:LASTEXITCODE = 0
  if ($args -contains "list") { return "[]" }
  if ($args -contains "start") { return '{"name":"execution1"}' }
  return ('{"properties":{"status":"' + $env:TEST_STATUS + '"}}')
}
function global:Start-Sleep {}
"""
    result = run_ps(SCRIPTS / "run-model-job.ps1", tmp_path, prelude,
                    env={"SUBSCRIPTION_ID": "test", "RESOURCE_GROUP": "rg-aivideo571",
                         "JOB_NAME": "download", "COMFY_APP_NAME": "comfyui", "TIMEOUT_SECONDS": "-1",
                         "TEST_STATUS": status})
    assert (result.returncode == 0) is success, result.stdout + result.stderr
    if success:
        assert "succeeded" in result.stdout
    elif status == "Running":
        assert "Timed out" in result.stderr


def test_model_job_refuses_active_queue(tmp_path):
    prelude = """
function global:az {
  $global:LASTEXITCODE = 0
  if ($args -contains "start") { throw "Should not submit model job" }
  if ($args -contains "execution" -and $args -contains "list") { return "[]" }
  return '[{"name":"comfyui","properties":{"configuration":{"ingress":{"fqdn":"comfy.test"}}}}]'
}
function global:Invoke-RestMethod { return @{queue_running=@(@(1,"prompt")); queue_pending=@()} }
"""
    result = run_ps(SCRIPTS / "run-model-job.ps1", tmp_path, prelude,
                    env={"SUBSCRIPTION_ID": "test", "RESOURCE_GROUP": "rg-aivideo571", "COMFY_APP_NAME": "comfyui"})
    assert result.returncode != 0 and "active or queued" in result.stderr


@pytest.mark.parametrize("secondary_status", ["busy", "offline", "invalid", "idle"])
def test_model_job_checks_both_workers_before_provisioning(tmp_path, secondary_status):
    prelude = """
$global:checked = @()
function global:az {
  $global:LASTEXITCODE = 0
  if ($args -contains "execution" -and $args -contains "list") { return "[]" }
  if ($args -contains "list") {
    return '[{"name":"comfyui","properties":{"configuration":{"ingress":{"fqdn":"primary.test"}}}},{"name":"comfyui-2","properties":{"configuration":{"ingress":{"fqdn":"secondary.test"}}}}]'
  }
  if ($args -contains "start") {
    if ($global:checked.Count -ne 2) { throw "Did not check both workers" }
    Write-Host "Both queues verified"
    return '{"name":"execution"}'
  }
  return '{"properties":{"status":"Succeeded"}}'
}
function global:Invoke-RestMethod {
  param($Uri, $TimeoutSec)
  $global:checked += $Uri
  if ($Uri -match "secondary") {
    if ($env:SECONDARY_STATUS -eq "busy") { return @{queue_running=@(@(1,"p")); queue_pending=@()} }
    if ($env:SECONDARY_STATUS -eq "offline") { throw "Worker unreachable" }
    if ($env:SECONDARY_STATUS -eq "invalid") { return @{} }
  }
  return @{queue_running=@(); queue_pending=@()}
}
"""
    result = run_ps(SCRIPTS / "run-model-job.ps1", tmp_path, prelude, env={
        "SUBSCRIPTION_ID": "test", "RESOURCE_GROUP": "rg-aivideo571",
        "JOB_NAME": "download", "COMFY_APP_NAMES": "comfyui,comfyui-2",
        "TIMEOUT_SECONDS": "1", "SECONDARY_STATUS": secondary_status,
    })
    assert (result.returncode == 0) is (secondary_status == "idle"), result.stdout + result.stderr
    assert ("Both queues verified" in result.stdout) is (secondary_status == "idle")


@pytest.mark.parametrize("existing_status", ["Succeeded", "Failed", "Running", "Unexpected"])
def test_model_job_waits_for_existing_execution_before_starting(tmp_path, existing_status):
    prelude = """
$global:existingChecked = $false
function global:az {
  $global:LASTEXITCODE = 0
  if ($args -contains "execution" -and $args -contains "list") {
    return '[{"name":"existing","properties":{"status":"Running"}}]'
  }
  if ($args -contains "show" -and $args -contains "existing") {
    $global:existingChecked = $true
    return ('{"properties":{"status":"' + $env:TEST_STATUS + '"}}')
  }
  if ($args -contains "list") { return "[]" }
  if ($args -contains "start") {
    if (-not $global:existingChecked -or $env:TEST_STATUS -ne "Succeeded") {
      throw "Started concurrent provisioning"
    }
    Write-Host "Submitted requested revision"
    return '{"name":"new"}'
  }
  return '{"properties":{"status":"Succeeded"}}'
}
function global:Start-Sleep {}
"""
    result = run_ps(SCRIPTS / "run-model-job.ps1", tmp_path, prelude, env={
        "SUBSCRIPTION_ID": "test", "RESOURCE_GROUP": "rg-aivideo571",
        "JOB_NAME": "download", "COMFY_APP_NAME": "comfyui", "TIMEOUT_SECONDS": "-1",
        "TEST_STATUS": existing_status,
    })
    assert (result.returncode == 0) is (existing_status == "Succeeded"), result.stdout + result.stderr
    assert ("Submitted requested revision" in result.stdout) is (existing_status == "Succeeded")
    assert "Started concurrent provisioning" not in result.stderr


@pytest.mark.parametrize("bad", ["old-group", "delete", "vm", "subscription", "none", "valid"])
def test_saved_plan_scope_guard(tmp_path, bad):
    changes = [{"mode": "managed", "type": "azurerm_resource_group", "address": "azurerm_resource_group.rg",
                "change": {"actions": ["create"], "before": None, "after": {"name": "rg-aivideo571"}}}]
    resource = {"mode": "managed", "type": "azurerm_container_app", "address": "azurerm_container_app.comfyui",
                "change": {"actions": ["create"], "before": None, "after": {"resource_group_name": "rg-aivideo571"}}}
    if bad == "old-group":
        resource["change"]["before"] = {"id": "/subscriptions/test/resourceGroups/rg-aivideo570/providers/Microsoft.App/containerApps/video"}
    elif bad == "delete":
        resource["change"]["actions"] = ["delete"]
    elif bad == "vm":
        resource["type"] = "azurerm_linux_virtual_machine"
    elif bad == "subscription":
        resource["change"]["after"]["id"] = "/subscriptions/wrong/resourceGroups/rg-aivideo571/providers/Microsoft.App/containerApps/video"
    elif bad == "none":
        changes = []
    changes.append(resource)
    fixture = tmp_path / "plan.json"
    fixture.write_text(json.dumps({"resource_changes": changes}), encoding="utf-8")
    saved = tmp_path / "release.tfplan"
    saved.touch()
    prelude = """
function global:terraform {
  $global:LASTEXITCODE = 0
  return (Get-Content -Raw -LiteralPath $env:PLAN_FIXTURE)
}
"""
    result = run_ps(SCRIPTS / "check-plan.ps1", tmp_path, prelude, env={"PLAN_FIXTURE": str(fixture)},
                    args=f"-Plan '{saved}'")
    assert (result.returncode == 0) is (bad == "valid"), result.stdout + result.stderr
