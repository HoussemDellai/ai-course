#!/bin/bash
set -euo pipefail

COMFY_DIR="${COMFY_DIR:-/root/ComfyUI}"
CONSTRAINTS="${COMFY_CONSTRAINTS:-/builder-scripts/constraints.txt}"
BOOTSTRAP="${COMFY_BOOTSTRAP_PATH:-/tmp/prepare-comfyui.sh}"
WORKER="${COMFY_WORKER:-primary}"
case "$WORKER" in
  primary) MEDIA_DIR="$COMFY_DIR" ;;
  secondary) MEDIA_DIR="$COMFY_DIR/workers/secondary" ;;
  *) echo "ERROR: COMFY_WORKER must be primary or secondary." >&2; exit 1 ;;
esac
[[ -s "$COMFY_DIR/.platform-models-ready" ]] || {
  echo "ERROR: model provisioning has not completed successfully." >&2
  exit 1
}
[[ "$(cat "$COMFY_DIR/.platform-models-ready")" == "$PROVISION_VERSION" ]] || {
  echo "ERROR: model workspace is not prepared for this revision." >&2
  exit 1
}
git config --global --add safe.directory "$COMFY_DIR"
printf '%s' "$COMFY_BOOTSTRAP_B64" | base64 --decode | tr -d '\r' > "$BOOTSTRAP"
COMFY_DIR="$COMFY_DIR" bash "$BOOTSTRAP"

# Keep the yanwk image's CUDA/PyTorch packages instead of letting requirements replace them.
[[ -s "$CONSTRAINTS" ]] || { echo "ERROR: image has no PyTorch constraints." >&2; exit 1; }
export PIP_ROOT_USER_ACTION=ignore
python3 -m pip install --constraint "$CONSTRAINTS" --requirement "$COMFY_DIR/requirements.txt"
python3 -c "import torch; assert torch.cuda.is_available(), 'CUDA unavailable'; print('torch', torch.__version__, 'cuda', torch.version.cuda)"
export GPU_STATS_CONTAINER=1
export PYTHONPYCACHEPREFIX=/tmp/comfyui-pycache
for directory in "$MEDIA_DIR/input" "$MEDIA_DIR/output" "$MEDIA_DIR/user"; do
  [[ -d "$directory" && -r "$directory" && -w "$directory" ]] || {
    echo "ERROR: worker directory is missing or inaccessible: $directory" >&2
    exit 1
  }
done
TEMP_DIR="${TMPDIR:-/tmp}/comfyui-$WORKER"
mkdir -p "$TEMP_DIR"
cd "$COMFY_DIR"
# Direct exec, rather than the upstream shell wrapper, lets ACA SIGTERM reach ComfyUI.
exec python3 main.py --listen 0.0.0.0 --port 8188 --disable-xformers \
  --input-directory "$MEDIA_DIR/input" --output-directory "$MEDIA_DIR/output" \
  --user-directory "$MEDIA_DIR/user" --temp-directory "$TEMP_DIR"
