#!/bin/bash
# Installs ComfyUI under /opt/comfyui and runs it as a systemd service on port 8188.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
COMFY_HOME=/opt/comfyui
COMFY_DIR=$COMFY_HOME/ComfyUI
VENV=$COMFY_HOME/venv

# The VM reboots after the driver install: wait for the driver to be available.
for i in $(seq 1 60); do
  nvidia-smi > /dev/null 2>&1 && break
  echo "Waiting for the NVIDIA driver... ($i/60)"
  sleep 10
done
nvidia-smi || { echo "ERROR: NVIDIA driver not available, check 01-install-nvidia-drivers.sh" >&2; exit 1; }

apt-get update -o DPkg::Lock::Timeout=600
apt-get install -y -o DPkg::Lock::Timeout=600 git python3 python3-pip python3-venv ffmpeg

mkdir -p $COMFY_HOME
if [ ! -d "$COMFY_DIR/.git" ]; then
  git clone https://github.com/comfyanonymous/ComfyUI.git $COMFY_DIR
else
  git -C $COMFY_DIR pull --ff-only || true
fi

[ -d "$VENV" ] || python3 -m venv $VENV
$VENV/bin/pip install --upgrade pip
# ComfyUI needs a cu130+ PyTorch build for the optimized CUDA ops on H100.
$VENV/bin/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
$VENV/bin/pip install -r $COMFY_DIR/requirements.txt
$VENV/bin/python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available in PyTorch'; print('torch', torch.__version__, 'cuda', torch.version.cuda)"

cat > /etc/systemd/system/comfyui.service <<EOF
[Unit]
Description=ComfyUI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$COMFY_DIR
ExecStart=$VENV/bin/python main.py --listen 0.0.0.0 --port 8188
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable comfyui
systemctl restart comfyui

for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:8188/system_stats > /dev/null && { echo "ComfyUI is up."; exit 0; }
  sleep 10
done
echo "ERROR: ComfyUI did not start, see 'journalctl -u comfyui'" >&2
exit 1
