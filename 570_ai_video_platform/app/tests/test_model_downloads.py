import os
from pathlib import Path
import shutil
import subprocess

import pytest

from video_platform.comfyui import load_workflow
from video_platform.video_models import VIDEO_MODELS

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "infra" / "scripts" / "03-download-models.sh"
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
BASH = str(GIT_BASH) if GIT_BASH.exists() else shutil.which("bash")
MODEL_INPUTS = {"unet_name", "clip_name", "vae_name", "model_name"}


def ltx_files():
    workflow = load_workflow(VIDEO_MODELS["ltx25"].workflow_path)
    return {value for node in workflow.values() for key, value in node["inputs"].items() if key in MODEL_INPUTS}


def test_main_downloader_contains_all_ltx25_weights():
    script = SCRIPT.read_text()
    assert len(ltx_files()) == 5
    assert all(name in script for name in ltx_files())
    wrapper = (SCRIPT.parent / "05-download-ltx25.sh").read_text()
    assert "03-download-models.sh" in wrapper and "safetensors" not in wrapper


@pytest.fixture
def downloader(tmp_path):
    if not BASH:
        pytest.skip("Bash is needed to execute downloader tests")
    models = tmp_path / "models"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wget = bin_dir / "wget"
    wget.write_text("#!/bin/bash\necho public >> \"$CALLS\"\n", encoding="utf-8")
    wget.chmod(0o755)
    curl = bin_dir / "curl"
    curl.write_text("""#!/bin/bash
set -eu
header=$(cat)
[[ "$header" == "Authorization: Bearer test-read-token" ]] || exit 90
[[ "$*" != *test-read-token* ]] || exit 91
echo gated >> "$CALLS"
dest=
while [[ $# -gt 0 ]]; do
  if [[ "$1" == --output ]]; then dest=$2; shift 2; else shift; fi
done
[[ -n "$dest" ]] || exit 92
if [[ "${EMPTY:-0}" == 1 ]]; then : > "$dest"; exit 0; fi
if [[ "${FAIL:-0}" == 1 ]]; then printf partial > "$dest"; exit 22; fi
printf complete > "$dest"
""", encoding="utf-8")
    curl.chmod(0o755)
    source = SCRIPT.read_text().replace("M=/opt/comfyui/ComfyUI/models", f'M="{models.as_posix()}"')
    calls = tmp_path / "calls"
    env = {**os.environ, "CALLS": calls.as_posix()}
    env.pop("HF_TOKEN", None)
    # Prefix inside Bash: Windows PATH uses semicolons, whereas Bash expects colon separators.
    bin_path = bin_dir.as_posix()
    if os.name == "nt":
        bin_path = f"/{bin_path[0].lower()}{bin_path[2:]}"
    source = f'export PATH="{bin_path}:$PATH"\n' + source

    def run(**variables):
        return subprocess.run([BASH, "-s"], input=source, text=True, capture_output=True,
                              env={**env, **variables}, timeout=30)

    return run, models, calls


def test_missing_token_fails_before_downloading(downloader):
    run, models, calls = downloader
    result = run()
    assert result.returncode != 0 and "Set HF_TOKEN" in result.stderr
    assert not calls.exists() and not models.exists()


def test_gated_downloads_resume_publish_and_skip(downloader):
    run, models, calls = downloader
    failed = run(HF_TOKEN="test-read-token", FAIL="1")
    assert failed.returncode != 0 and "failed to download" in failed.stderr
    assert len(list(models.rglob("*.part"))) == 1
    assert not list(models.rglob("*.safetensors"))
    success = run(HF_TOKEN="test-read-token")
    assert success.returncode == 0, success.stderr
    assert {p.name for p in models.rglob("*.safetensors")} == ltx_files()
    assert not list(models.rglob("*.part"))
    assert "test-read-token" not in success.stdout + success.stderr
    before = calls.read_text().splitlines().count("gated")
    again = run()
    assert again.returncode == 0, again.stderr
    assert calls.read_text().splitlines().count("gated") == before
    assert "All models downloaded." in again.stdout


def test_empty_download_is_not_published(downloader):
    run, models, _ = downloader
    result = run(HF_TOKEN="test-read-token", EMPTY="1")
    assert result.returncode != 0 and "empty download" in result.stderr
    assert not list(models.rglob("*.safetensors"))
