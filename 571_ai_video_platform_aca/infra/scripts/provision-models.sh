#!/bin/bash
set +x
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates git wget curl util-linux
COMFY_DIR="${COMFY_DIR:-/root/ComfyUI}"
mkdir -p "$COMFY_DIR"
exec 9>"$COMFY_DIR/.provision.lock"
flock -n 9 || { echo "ERROR: another provisioning execution is running." >&2; exit 1; }
rm -f "$COMFY_DIR/.platform-models-ready"

printf '%s' "$COMFY_BOOTSTRAP_B64" | base64 --decode | tr -d '\r' > /tmp/prepare-comfyui.sh
COMFY_DIR="$COMFY_DIR" bash /tmp/prepare-comfyui.sh
mkdir -p "$COMFY_DIR/input" "$COMFY_DIR/output" "$COMFY_DIR/temp"
chown 10000:10000 "$COMFY_DIR/input" "$COMFY_DIR/output" "$COMFY_DIR/temp"
mkdir -p "$COMFY_DIR/user" "$COMFY_DIR/workers/secondary/input" \
  "$COMFY_DIR/workers/secondary/output" "$COMFY_DIR/workers/secondary/user"
chown 10000:10000 "$COMFY_DIR/user" "$COMFY_DIR/workers/secondary/input" \
  "$COMFY_DIR/workers/secondary/output" "$COMFY_DIR/workers/secondary/user"
mkdir -p "$COMFY_DIR/custom_nodes/platform_gpu"
printf '%s' "$GPU_EXPORTER_B64" | base64 --decode | tr -d '\r' > "$COMFY_DIR/custom_nodes/platform_gpu/gpu_stats_exporter.py"
printf '%s' "$GPU_EXTENSION_B64" | base64 --decode | tr -d '\r' > "$COMFY_DIR/custom_nodes/platform_gpu/__init__.py"
printf '%s' "$MODEL_DOWNLOADER_B64" | base64 --decode | tr -d '\r' > /tmp/download-models.sh
MODEL_DIR="$COMFY_DIR/models" bash /tmp/download-models.sh
printf '%s\n' "$PROVISION_VERSION" > "$COMFY_DIR/.platform-models-ready.tmp"
mv "$COMFY_DIR/.platform-models-ready.tmp" "$COMFY_DIR/.platform-models-ready"
