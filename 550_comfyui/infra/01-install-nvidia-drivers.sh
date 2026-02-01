#!/bin/bash

################################
### 1. Install CUDA Drivers
################################

# 1. Install ubuntu-drivers utility:
sudo apt update
sudo apt install ubuntu-drivers-common -y

# 2. Install the latest NVIDIA drivers:
sudo ubuntu-drivers install

# 3. Reboot the VM after the GPU driver is installed:
# sudo reboot # needed ?

# 4. Download and install the CUDA toolkit from NVIDIA:
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda-toolkit-13-1
# check new Cuda versions here: https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=Ubuntu&target_version=24.04&target_type=deb_network
# sudo apt install ./cuda-keyring_1.1-1_all.deb -y
# sudo apt update
# sudo apt install cuda-toolkit-13-1 -y

# 5. Reboot the VM after installation completes:
# sudo reboot

# 6. Verify that the GPU is correctly recognized (after reboot):
nvidia-smi

# 7. We recommend that you periodically update NVIDIA drivers after deployment.
sudo apt update
sudo apt full-upgrade -y

sudo reboot
