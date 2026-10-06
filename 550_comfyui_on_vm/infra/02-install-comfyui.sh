#!/bin/bash
set -eo pipefail

export DEBIAN_FRONTEND=noninteractive

###################################
### 2. Install ComfyUI on Ubuntu
###################################

# Step 0: Make sure the NVIDIA driver is loaded (the VM reboots after installing it)
for i in $(seq 1 30); do
  nvidia-smi > /dev/null 2>&1 && break
  echo "Waiting for NVIDIA driver to be available... ($i/30)"
  sleep 10
done
if ! nvidia-smi; then
  echo "ERROR: NVIDIA driver not available. Check the output of 01-install-nvidia-drivers.sh" >&2
  exit 1
fi

# Step 1: System Environment Preparation
# ComfyUI requires Python 3.12 or higher (Python 3.13 is recommended). Check your Python version:
python3 --version

# If Python is not installed or the version is too low, install it following these steps:
sudo apt-get update -o DPkg::Lock::Timeout=600
sudo apt-get install -y -o DPkg::Lock::Timeout=600 python3 python3-pip python3-venv

# Create Virtual Environment
# Using a virtual environment can avoid package conflict issues
python3 -m venv comfy-env
 
# Activate the virtual environment
source comfy-env/bin/activate
# Note: You need to activate the virtual environment each time before using ComfyUI. To exit the virtual environment, use the deactivate command.

# Step 2: Install Comfy CLI
# Install comfy-cli in the activated virtual environment:
pip install comfy-cli

# Step 3: Install ComfyUI using Comfy CLI with NVIDIA GPU Support and PyTorch for CUDA 13.0 (cu130)
# Without --cuda-version, comfy installs a cu126 build of PyTorch (ComfyUI needs cu130+ for optimized CUDA ops)
# use 'yes' to accept all prompts ('yes' gets SIGPIPE when comfy exits, so disable pipefail here)
set +o pipefail
yes | comfy install --nvidia --cuda-version 13.0
set -o pipefail

# Step 4: Verify PyTorch can use the GPU
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available in PyTorch'; print('torch', torch.__version__, 'cuda', torch.version.cuda)"

# Step 5. Launch ComfyUI
# By default, ComfyUI will run on http://localhost:8188.
# and don't forget the double -- 
comfy launch --background -- --listen 0.0.0.0 --port 8188
