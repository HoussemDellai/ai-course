# Running Text to Image and Text to Video with ComfyUI and Nvidia H100 GPU

This guide provides instructions on how to set up and run Text to Image and Text to Video generation using ComfyUI with an Nvidia H100 GPU.

## Steps to create the infrastructure

### 1. Create a Virtual Machine with Nvidia H100 GPU

Create an Azure virtual machine with `Nvidia H100` GPUs like sku: `Standard NC40ads H100 v5`. Choose a Linux distribution of your choice like `Ubuntu Pro 24.04`.

### 2. Install CUDA Drivers

SSH into the Ubuntu VM and install the CUDA drivers by following the official Microsoft documentation: [Install CUDA drivers on N-series VMs](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/n-series-driver-setup#install-cuda-drivers-on-n-series-vms).

```sh
# 1. Install ubuntu-drivers utility:
sudo apt update && sudo apt install -y ubuntu-drivers-common

# 2. Install the latest NVIDIA drivers:
sudo ubuntu-drivers install

# 3. Reboot the VM after the GPU driver is installed:
sudo reboot

# 4. Download and install the CUDA toolkit from NVIDIA:
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo apt install -y ./cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt -y install cuda-toolkit-12-5

# 5. Reboot the VM after installation completes:
sudo reboot

# 6. Verify that the GPU is correctly recognized (after reboot):
nvidia-smi

# 7. We recommend that you periodically update NVIDIA drivers after deployment.
sudo apt update
sudo apt full-upgrade
```

### 3. Install ComfyUI on Ubuntu

Follow the instructions from the ComfyUI Wiki to install ComfyUI on your Ubuntu VM using Comfy CLI: [Install ComfyUI using Comfy CLI](https://comfyui-wiki.com/en/install/install-comfyui/install-comfyui-on-linux).

```sh
# Step 1: System Environment Preparation
# ComfyUI requires Python 3.12 or higher (Python 3.13 is recommended). Check your Python version:
python3 --version

# If Python is not installed or the version is too low, install it following these steps:
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Create Virtual Environment
# Using a virtual environment can avoid package conflict issues:
# Create a virtual environment named comfy-env
python3 -m venv comfy-env
 
# Activate the virtual environment
source comfy-env/bin/activate
# Note: You need to activate the virtual environment each time before using ComfyUI. To exit the virtual environment, use the deactivate command.

# Step 2: Install Comfy CLI
# Install comfy-cli in the activated virtual environment:

pip install comfy-cli

# Configure Command Line Auto-completion (Optional)
# To get a better user experience, you can enable command line auto-completion:

comfy --install-completion

# Step 3: Install ComfyUI
# Installing ComfyUI with comfy-cli is very simple, requiring just one command:
comfy install

# Step 4: Install GPU Support
# NVIDIA GPU (CUDA)
# If you’re using an NVIDIA GPU, you need to install CUDA support:

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu130

# Note: Please choose the corresponding PyTorch version based on your CUDA version. Visit the PyTorch website for the latest installation commands.

# Step 5: Launch ComfyUI
# After installation is complete, launch ComfyUI:
comfy launch

# By default, ComfyUI will run on http://localhost:8188.

# Common Launch Options
# Specify listen address and port
# and don't forget the double -- 
comfy launch -- --listen 0.0.0.0 --port 8080
 
# Use CPU mode
comfy launch -- --cpu
 
# Low VRAM mode
comfy launch -- --lowvram
 
# Ultra-low VRAM mode
comfy launch -- --novram

# Note: The --background parameter may no longer be supported in some versions of ComfyUI. If you need to run in the background, consider using system-level tools such as nohup or screen.
```

## Sources

- [Install CUDA drivers on N-series VMs](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/n-series-driver-setup#install-cuda-drivers-on-n-series-vms)
- [Install ComfyUI using Comfy CLI](https://comfyui-wiki.com/en/install/install-comfyui/install-comfyui-on-linux)