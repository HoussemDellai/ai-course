#!/bin/bash
# Installs the NVIDIA driver + CUDA toolkit, then schedules a reboot.
# Idempotent: exits early when the driver is already loaded.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
APT_OPTS="-y -o DPkg::Lock::Timeout=600"

if nvidia-smi > /dev/null 2>&1; then
  echo "NVIDIA driver already loaded, nothing to do."
  nvidia-smi
  exit 0
fi

# cloud-init configures the apt sources at first boot, wait for it.
cloud-init status --wait || true

apt-get update -o DPkg::Lock::Timeout=600
apt-get install $APT_OPTS ubuntu-drivers-common
ubuntu-drivers install

if ! command -v nvidia-smi > /dev/null; then
  echo "ERROR: NVIDIA driver installation failed (nvidia-smi not found)" >&2
  exit 1
fi

wget -q -O /tmp/cuda-keyring.deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i /tmp/cuda-keyring.deb
apt-get update -o DPkg::Lock::Timeout=600
apt-get install $APT_OPTS cuda-toolkit-13-1

# Reboot in 1 minute so this Run Command can report success before the VM goes down.
shutdown -r +1 "Rebooting to load the NVIDIA driver"
echo "NVIDIA driver installed, reboot scheduled."
