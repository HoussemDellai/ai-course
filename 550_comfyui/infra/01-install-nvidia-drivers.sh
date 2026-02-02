#!/bin/bash

################################
### 1. Install CUDA Drivers
################################

# 1. Install ubuntu-drivers utility:
sudo apt-get update
sudo apt-get install ubuntu-drivers-common -y

# 2. Install the latest NVIDIA drivers:
sudo ubuntu-drivers install

# 3. Download and install the CUDA toolkit from NVIDIA:
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get install cuda-toolkit-13-1 -y

# 4. Reboot the system to apply changes
sudo reboot

# # 5. Verify that the GPU is correctly recognized (after reboot):
# nvidia-smi

# # 6. We recommend that you periodically update NVIDIA drivers after deployment.
# sudo apt-get update
# sudo apt-get full-upgrade -y
