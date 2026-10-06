#!/bin/bash
# Fail fast so Run Command reports errors instead of silently succeeding
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
APT_OPTS="-y -o DPkg::Lock::Timeout=600"

################################
### 1. Install CUDA Drivers
################################

# 0. Wait for cloud-init to finish: it configures the Ubuntu apt sources at first boot.
#    Running apt before that results in "Unable to locate package ubuntu-drivers-common".
cloud-init status --wait || true

# 1. Install ubuntu-drivers utility:
sudo apt-get update -o DPkg::Lock::Timeout=600
sudo apt-get install $APT_OPTS ubuntu-drivers-common

# 2. Install the latest NVIDIA drivers:
sudo ubuntu-drivers install

# Make sure the driver was actually installed
if ! command -v nvidia-smi > /dev/null; then
  echo "ERROR: NVIDIA driver installation failed (nvidia-smi not found)" >&2
  exit 1
fi

# 3. Download and install the CUDA toolkit from NVIDIA:
wget -q -O cuda-keyring_1.1-1_all.deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update -o DPkg::Lock::Timeout=600
sudo apt-get install $APT_OPTS cuda-toolkit-13-1

# 4. Reboot the system to apply changes
sudo reboot

# [Optional] 5. Verify that the GPU is correctly recognized (after reboot):
# nvidia-smi

# [Optional] 6. We recommend that you periodically update NVIDIA drivers after deployment.
# sudo apt-get update
# sudo apt-get full-upgrade -y
