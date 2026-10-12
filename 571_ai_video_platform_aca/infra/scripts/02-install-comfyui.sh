#!/bin/bash
set -euo pipefail

COMFY_DIR="${COMFY_DIR:-/root/ComfyUI}"
COMFYUI_VERSION=v0.39.0
COMFYUI_COMMIT=b0b743566f65daafc423b4fea8a2fbda94b3384a

mkdir -p "$COMFY_DIR"
if [[ ! -d "$COMFY_DIR/.git" ]]; then
  git -C "$COMFY_DIR" init
  git -C "$COMFY_DIR" remote add origin https://github.com/Comfy-Org/ComfyUI.git
fi
if ! git -C "$COMFY_DIR" rev-parse --verify HEAD > /dev/null 2>&1; then
  git -C "$COMFY_DIR" fetch --depth 1 origin "refs/tags/$COMFYUI_VERSION"
  actual=$(git -C "$COMFY_DIR" rev-parse FETCH_HEAD)
  [[ "$actual" == "$COMFYUI_COMMIT" ]] || { echo "ERROR: ComfyUI release checksum changed." >&2; exit 1; }
  git -C "$COMFY_DIR" checkout --detach "$COMFYUI_COMMIT"
fi

actual=$(git -C "$COMFY_DIR" rev-parse HEAD)
[[ "$actual" == "$COMFYUI_COMMIT" ]] || {
  echo "ERROR: workspace contains a different ComfyUI release; upgrade explicitly between jobs." >&2
  exit 1
}
[[ -f "$COMFY_DIR/main.py" ]] || { echo "ERROR: incomplete ComfyUI workspace." >&2; exit 1; }
echo "ComfyUI $COMFYUI_VERSION ($actual) prepared."
