#!/bin/bash
# Installs the GPU stats exporter (gpu_stats_exporter.py) as a systemd service on port 8189.
# Terraform substitutes the base64 of the exporter below (see vm_comfyui.tf). Idempotent, doesn't touch ComfyUI.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
INSTALL_DIR=/opt/gpu-stats
PORT=8189

# The VM reboots after the driver install: wait for the driver to be available.
for i in $(seq 1 60); do
  nvidia-smi > /dev/null 2>&1 && break
  echo "Waiting for the NVIDIA driver... ($i/60)"
  sleep 10
done
nvidia-smi > /dev/null || { echo "ERROR: NVIDIA driver not available, check 01-install-nvidia-drivers.sh" >&2; exit 1; }

command -v python3 > /dev/null || {
  apt-get update -o DPkg::Lock::Timeout=600
  apt-get install -y -o DPkg::Lock::Timeout=600 python3
}

mkdir -p $INSTALL_DIR
echo "__EXPORTER_B64__" | base64 -d > $INSTALL_DIR/gpu_stats_exporter.py
chmod 755 $INSTALL_DIR/gpu_stats_exporter.py

cat > /etc/systemd/system/gpu-stats.service <<EOF
[Unit]
Description=GPU stats exporter (nvidia-smi over HTTP)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/gpu_stats_exporter.py
Environment=GPU_STATS_PORT=$PORT
DynamicUser=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable gpu-stats
systemctl restart gpu-stats

for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:$PORT/gpu_stats; then
    echo
    echo "GPU stats exporter is up on port $PORT."
    exit 0
  fi
  sleep 2
done
echo "ERROR: GPU stats exporter did not start, see 'journalctl -u gpu-stats'" >&2
exit 1
