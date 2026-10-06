#!/bin/bash
# Downloads the LTX-2.5 22B distilled weights (about 37 GB) used by the 'ltx25' video model.
# Not run by Terraform: the Lightricks/LTX-2.5 repository on Hugging Face is gated, so it needs a token.
#   1. Accept the license on https://huggingface.co/Lightricks/LTX-2.5 (access is granted right away).
#   2. Create a read token on https://huggingface.co/settings/tokens.
#   3. On the VM: sudo HF_TOKEN=hf_xxx bash 05-download-ltx25.sh
# Idempotent: 'wget -c' resumes partial downloads and skips completed files.
# ComfyUI is only updated and restarted when it doesn't have the LTX-2.5 nodes yet. A restart drops the clip being
# rendered, so run this between jobs.
set -euo pipefail

if [ -z "${HF_TOKEN:-}" ]; then
  echo "ERROR: set HF_TOKEN to a Hugging Face read token, e.g. 'sudo HF_TOKEN=hf_xxx bash $0'" >&2
  exit 1
fi

COMFY_HOME=/opt/comfyui
COMFY_DIR=$COMFY_HOME/ComfyUI
VENV=$COMFY_HOME/venv
M=$COMFY_DIR/models
REPO=https://huggingface.co/Lightricks/LTX-2.5/resolve/main
AUTH="Authorization: Bearer $HF_TOKEN"

# A gated repo answers 401/403 until the license is accepted with the token's account.
status=$(curl -s -o /dev/null -w '%{http_code}' -I -H "$AUTH" "$REPO/vae/ltx-2.5-audio-vae-bf16.safetensors")
case "$status" in
  2*|3*) ;;
  401) echo "ERROR: Hugging Face rejected HF_TOKEN (HTTP 401). Check the token." >&2; exit 1 ;;
  403) echo "ERROR: no access to Lightricks/LTX-2.5 (HTTP 403). Accept the license on the model page first." >&2; exit 1 ;;
  *) echo "ERROR: unexpected HTTP $status from Hugging Face." >&2; exit 1 ;;
esac

mkdir -p $M/diffusion_models $M/text_encoders $M/vae $M/latent_upscale_models
dl() { wget -q -c --header="$AUTH" -P "$M/$1" "$REPO/$2"; echo "OK $1/$(basename "$2")"; }

dl diffusion_models      diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors
dl text_encoders         text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors
dl vae                   vae/ltx-2.5-video-vae-bf16.safetensors
dl vae                   vae/ltx-2.5-audio-vae-bf16.safetensors
dl latent_upscale_models latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors

if curl -sf http://127.0.0.1:8188/object_info/LTXVDualCFGGuider | grep -q LTXVDualCFGGuider; then
  echo "ComfyUI already has the LTX-2.5 nodes: no update needed."
else
  echo "Updating ComfyUI for the LTX-2.5 nodes..."
  git -C $COMFY_DIR pull --ff-only
  $VENV/bin/pip install -r $COMFY_DIR/requirements.txt
  systemctl restart comfyui
  for i in $(seq 1 30); do
    curl -sf http://127.0.0.1:8188/system_stats > /dev/null && break
    sleep 10
  done
fi

# ComfyUI lists model files when a prompt is validated, so new files are picked up without a restart.
echo "LTX-2.5 is ready: use video_model 'ltx25'."
