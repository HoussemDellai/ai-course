#!/bin/bash
# Downloads the models used by the platform (about 262 GB in total):
# text-to-video and image-to-video for the 4 video models, Qwen-Image-Edit for the keyframes of videos built
# from a reference photo, MiniMax Music 3 for the background music and SeedVR2 for 1080p / 4K upscaling.
# LTX-2.5 is gated on Hugging Face: missing LTX-2.5 weights need HF_TOKEN from an account with access to
# Lightricks/LTX-2.5 (already-installed weights don't). Without HF_TOKEN they are skipped with a warning, so
# Terraform (which never receives the token) still installs every public model; rerun with HF_TOKEN afterwards.
# Public downloads resume with wget; gated downloads are published only after curl succeeds.
set +x
set -euo pipefail

M=/opt/comfyui/ComfyUI/models
LTX25=https://huggingface.co/Lightricks/LTX-2.5/resolve/main
LTX25_FILES=(
  diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors
  text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors
  vae/ltx-2.5-video-vae-bf16.safetensors
  vae/ltx-2.5-audio-vae-bf16.safetensors
  latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors
)
SKIPPED=0
mkdir -p $M/text_encoders $M/vae $M/diffusion_models $M/loras $M/checkpoints $M/latent_upscale_models $M/clip_vision

dl() { wget -q -c -P "$M/$1" "$2"; echo "OK $1/$(basename "$2")"; }

dl_gated() {
  local dest="$M/$1"
  if [[ -s "$dest" ]]; then
    echo "OK $1 (already installed)"
    return
  fi
  if [[ -z "${HF_TOKEN:-}" ]]; then
    echo "WARNING: skipped $1: set HF_TOKEN to a read token with access to Lightricks/LTX-2.5." >&2
    SKIPPED=$((SKIPPED + 1))
    return
  fi
  # stdin keeps the token out of process arguments; curl strips Authorization on cross-host redirects.
  if ! printf 'Authorization: Bearer %s\n' "$HF_TOKEN" |
    curl --fail --location --silent --show-error --retry 3 --connect-timeout 30 \
      --proto '=https' --proto-redir '=https' --header @- --continue-at - \
      --output "$dest.part" "$LTX25/$1"; then
    echo "ERROR: failed to download $1. Check HF_TOKEN and model access; rerun to resume the .part file." >&2
    return 1
  fi
  if [[ ! -s "$dest.part" ]]; then
    echo "ERROR: empty download for $1" >&2
    return 1
  fi
  mv "$dest.part" "$dest"
  echo "OK $1"
}

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
# LTX-2.5 22B distilled (LTX-2.x Community License, gated on Hugging Face)
# Separate transformer, text encoder, video/audio VAEs and spatial upscaler.
########################################################
for file in "${LTX25_FILES[@]}"; do
  dl_gated "$file"
done

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

########################################################
# MiniMax Music 3 (MiniMax-Music3 Community License): instrumental background music per scene (opt-in 'music').
# ComfyUI repack: fp16 DiT, pruned int8 text encoder (8B global LLM + local LLM) and DAV audio VAE, about 13.4 GB.
########################################################
MM3=https://huggingface.co/Comfy-Org/MiniMax-Music-3/resolve/main
dl diffusion_models $MM3/diffusion_models/minimax_music3_dit_fp16.safetensors
dl text_encoders    $MM3/text_encoders/minimax_music3_text_encoder_pruned_int8_convrot.safetensors
dl vae              $MM3/vae/minimax_music3_dav.safetensors

########################################################
# SeedVR2 7B (Apache 2.0, native ComfyUI nodes): opt-in 1080p / 4K upscaling of every shot ('upscaler': 'seedvr2').
# fp16 one-step restoration DiT (16.5 GB) and its VAE (0.5 GB).
########################################################
SVR=https://huggingface.co/Comfy-Org/SeedVR2/resolve/main
dl diffusion_models $SVR/diffusion_models/seedvr2_7b_fp16.safetensors
dl vae              $SVR/vae/seedvr2_ema_vae_fp16.safetensors

if (( SKIPPED )); then
  echo "Public models downloaded; $SKIPPED LTX-2.5 file(s) skipped. Rerun with HF_TOKEN to enable LTX-2.5."
else
  echo "All models downloaded."
fi
