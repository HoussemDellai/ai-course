#!/bin/bash
# Downloads the models used by the platform (about 190 GB in total):
# text-to-video and image-to-video for the 3 video models, plus Qwen-Image-Edit for the keyframes
# of videos built from a reference photo.
# Idempotent: 'wget -c' resumes partial downloads and skips completed files.
set -euo pipefail

M=/opt/comfyui/ComfyUI/models
mkdir -p $M/text_encoders $M/vae $M/diffusion_models $M/loras $M/checkpoints $M/latent_upscale_models $M/clip_vision

dl() { wget -q -c -P "$M/$1" "$2"; echo "OK $1/$(basename "$2")"; }

########################################################
# Wan 2.2 14B text-to-video (Apache 2.0)
########################################################
WAN=https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files
dl text_encoders    https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
dl vae              $WAN/vae/wan_2.1_vae.safetensors
dl diffusion_models $WAN/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors
dl diffusion_models $WAN/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors
dl loras            $WAN/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors
dl loras            $WAN/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors
# image-to-video (videos built from a reference photo)
dl diffusion_models $WAN/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors
dl diffusion_models $WAN/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors
dl loras            $WAN/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors
dl loras            $WAN/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors

########################################################
# LTX-2 19B distilled, video + synchronized audio (LTX-2 Community License)
# The same checkpoint does text-to-video and image-to-video.
########################################################
dl checkpoints           https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled.safetensors
dl latent_upscale_models https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors
dl text_encoders         https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors

########################################################
# HunyuanVideo 1.5 720p text-to-video (Tencent Hunyuan Community License)
########################################################
HY=https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files
dl diffusion_models $HY/diffusion_models/hunyuanvideo1.5_720p_t2v_fp16.safetensors
dl text_encoders    $HY/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
dl text_encoders    $HY/text_encoders/byt5_small_glyphxl_fp16.safetensors
dl vae              $HY/vae/hunyuanvideo15_vae_fp16.safetensors
# image-to-video
dl diffusion_models $HY/diffusion_models/hunyuanvideo1.5_720p_i2v_fp16.safetensors
dl clip_vision      $HY/clip_vision/sigclip_vision_patch14_384.safetensors

########################################################
# Qwen-Image-Edit-2511 + 4-step Lightning LoRA (Apache 2.0): per-shot keyframes from the reference photo.
# Its text encoder (qwen_2.5_vl_7b_fp8_scaled) is the one HunyuanVideo 1.5 already uses.
########################################################
QIE=https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files
dl diffusion_models $QIE/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors
dl vae              https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors
dl loras            https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors

echo "All models downloaded."
