# !/bin/bash

# if folder doesn't exist create it
mkdir -p /root/comfy/ComfyUI/

cd /root/comfy/ComfyUI/

# if folder doesn't exist create it
mkdir -p models/text_encoders models/vae models/diffusion_models models/loras

########################################################
# Download the Z-Image-Turbo Text to Image components
########################################################

# 1. text encoder
wget -O models/text_encoders/qwen_3_4b.safetensors \
  https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors

# 2. VAE
wget -O models/vae/ae.safetensors \
  https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors

# 3. diffusion model
wget -O models/diffusion_models/z_image_turbo_bf16.safetensors \
  https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors

# 4. Lora
wget -O models/loras/pixel_art_style_z_image_turbo.safetensors \
  https://huggingface.co/tarn59/pixel_art_style_lora_z_image_turbo/resolve/main/pixel_art_style_z_image_turbo.safetensors
  
# comfy model download --relative-path models/text_encoders/ --filename qwen_3_4b.safetensors --url https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors

# comfy model download --relative-path models/vae --filename ae.safetensors --url https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors

# comfy model download --relative-path models/diffusion_models/ --filename z_image_turbo_bf16.safetensors --url https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors

# comfy model download --relative-path models/loras/ --filename pixel_art_style_z_image_turbo.safetensors --url https://huggingface.co/tarn59/pixel_art_style_lora_z_image_turbo/resolve/main/pixel_art_style_z_image_turbo.safetensors

################################################
# Download Wan 2.2 Text to Video components
################################################

# 1. text encoder
wget -O models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
  https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors

# 2. VAE
wget -O models/vae/wan_2.1_vae.safetensors \
  https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors

# 3. diffusion model (low noise)
wget -O models/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors \
  https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors

# 4. diffusion model (high noise)
wget -O models/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors \
  https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors

# 5. Lora (high noise)
wget -O models/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors \
  https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors

# 6. Lora (low noise) – filename inferred from URL
wget -O models/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors \
  https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors

######################################################
# Download QWEN Image 2512 Text to Image components
######################################################

wget -O models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors \
  https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors

wget -O models/vae/qwen_image_vae.safetensors \
  https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors

wget -O models/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors \
  https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors

wget -O models/loras/Qwen-Image-Lightning-4steps-V1.0.safetensors \
  https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V1.0.safetensors

# ######################################################
# # Download Flux 2 Klein Text to Image components
# ######################################################

# wget -P models/text_encoders/ https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors

# wget -P models/vae/ https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors

# wget -P models/diffusion_models/ https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors

# wget -P models/diffusion_models/ https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/main/flux-2-klein-9b-fp8.safetensors