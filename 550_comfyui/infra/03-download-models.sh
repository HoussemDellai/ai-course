# !/bin/bash

source comfy-env/bin/activate

cd comfy/ComfyUI/

# 1. text encoder
wget -O models/text_encoders/qwen_3_4b.safetensors https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors

# 2. VAE
wget -O models/vae/ae.safetensors https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors
# 3. diffusion model
wget -O models/diffusion_models/z_image_turbo_bf16.safetensors https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors

# 4. Lora
wget -O models/loras/pixel_art_style_z_image_turbo.safetensors https://huggingface.co/tarn59/pixel_art_style_lora_z_image_turbo/resolve/main/pixel_art_style_z_image_turbo.safetensors
# comfy model download --relative-path models/text_encoders/ --filename qwen_3_4b.safetensors --url https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors

# comfy model download --relative-path models/vae --filename ae.safetensors --url https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors

# comfy model download --relative-path models/diffusion_models/ --filename z_image_turbo_bf16.safetensors --url https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors

# comfy model download --relative-path models/loras/ --filename pixel_art_style_z_image_turbo.safetensors --url https://huggingface.co/tarn59/pixel_art_style_lora_z_image_turbo/resolve/main/pixel_art_style_z_image_turbo.safetensors