# !/bin/bash

###################################
### 2. Install ComfyUI on Ubuntu
###################################

# Step 1: System Environment Preparation
# ComfyUI requires Python 3.12 or higher (Python 3.13 is recommended). Check your Python version:
python3 --version

# If Python is not installed or the version is too low, install it following these steps:
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

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
# use 'yes' to accept all prompts
yes | comfy install --nvidia

# Step 4: Install GPU Support
# NVIDIA GPU (CUDA)
# If you’re using an NVIDIA GPU, you need to install CUDA support:

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu130

# Note: Please choose the corresponding PyTorch version based on your CUDA version. Visit the PyTorch website for the latest installation commands.

# Step 5: Launch ComfyUI
# After installation is complete, launch ComfyUI, by default on port 8188:
# comfy launch

# By default, ComfyUI will run on http://localhost:8188.

# Common Launch Options
# Specify listen address and port
# and don't forget the double -- 
comfy launch --background -- --listen 0.0.0.0 --port 8080
