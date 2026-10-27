variable "prefix" {
  description = "Short unique suffix used in resource names (lowercase letters and digits)."
  type        = string
  default     = "aivideo571"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{4,15}$", var.prefix)) && var.prefix != "aivideo570"
    error_message = "Use 5-16 lowercase alphanumeric characters, starting with a letter; aivideo570 is reserved for the existing deployment."
  }
}

variable "location" {
  description = "Region for Foundry, Blob storage and ACR. Must support the configured Foundry deployment."
  type        = string
  default     = "germanywestcentral"
}

variable "aca_location" {
  description = "Region for the GPU-capable ACA environment, VNet and Premium NFS storage."
  type        = string
  default     = "italynorth"
}

variable "subscription_id" {
  description = "Explicit deployment subscription; used by both providers and deployment scripts."
  type        = string
  default     = "2524a5e1-00d7-43c2-a7cf-a87b79df2415"
}

# variable "comfyui_cpu" {
#   description = "A100 container vCPU allocation. Required: choose after profiling; no unverified production default."
#   type        = number
#   validation {
#     condition     = var.comfyui_cpu >= 0.25 && var.comfyui_cpu <= 24 && var.comfyui_cpu * 4 == floor(var.comfyui_cpu * 4)
#     error_message = "A100 CPU must be 0.25-24 in increments of 0.25; verify the selected allocation in the target region."
#   }
# }

variable "comfyui_worker_count" {
  description = "Maximum always-on A100 ComfyUI workers. The secondary inventory entry is commented out; uncomment it and set 2 to restore parallel renders. Drain and approve secondary deletion before disabling it."
  type        = number
  default     = 1
  validation {
    condition     = contains([1, 2], var.comfyui_worker_count)
    error_message = "comfyui_worker_count must be 1 or 2."
  }
}

variable "comfyui_memory_gib" {
  description = "A100 container system RAM in GiB, separate from GPU VRAM. Validate with real enabled workflows."
  type        = number
  default     = 4
  validation {
    condition     = var.comfyui_memory_gib >= 0.5 && var.comfyui_memory_gib <= 220 && var.comfyui_memory_gib * 2 == floor(var.comfyui_memory_gib * 2)
    error_message = "A100 RAM must be 0.5-220 GiB in increments of 0.5; verify the selected allocation in the target region."
  }
}

variable "comfyui_image" {
  description = "Immutable yanwk boot image; validate bundled PyTorch and CUDA against the regional driver before deployment."
  type        = string
  default     = "yanwk/comfyui-boot:cu126-slim@sha256:3cc39449e0a425cc64088ac4d60ef3950b44cab7e6f9cdf702c540a1943eed1b"
  validation {
    condition     = can(regex("^yanwk/comfyui-boot:[a-zA-Z0-9._-]+@sha256:[a-f0-9]{64}$", var.comfyui_image))
    error_message = "Use a digest-pinned yanwk/comfyui-boot image."
  }
}

variable "model_storage_gib" {
  description = "Premium NFS capacity for the full model inventory and persistent working media."
  type        = number
  default     = 1024
  validation {
    condition     = var.model_storage_gib >= 512 && var.model_storage_gib == floor(var.model_storage_gib)
    error_message = "Provision at least 512 GiB for models and working media."
  }
}

variable "download_education_images" {
  description = "Include the checksum-verified Qwen-Image model used by educational illustrations."
  type        = bool
  default     = false
}

variable "model_download_timeout_seconds" {
  description = "Timeout for the complete model-download job, not a fire-and-forget job start."
  type        = number
  default     = 21600
  validation {
    condition     = var.model_download_timeout_seconds >= 1800 && var.model_download_timeout_seconds <= 86400
    error_message = "Model download timeout must be between 1800 and 86400 seconds."
  }
}

variable "hf_token_secret_id" {
  description = "Optional Key Vault secret URI containing an authorized HF read token. Grant the app identity secret-read access separately. Preferred over storing hf_token in state."
  type        = string
  default     = ""
  validation {
    condition     = var.hf_token_secret_id == "" || can(regex("^https://[a-zA-Z0-9-]+\\.vault\\.azure\\.net/secrets/[^/]+(/[^/]+)?$", var.hf_token_secret_id))
    error_message = "Use an Azure Key Vault secret URI, not the token value."
  }
}

variable "hf_token" {
  description = "Optional HF read token stored as a Container Apps secret. WARNING: persists in Terraform state and saved plans. Supply through TF_VAR_hf_token, not committed files. Mutually exclusive with hf_token_secret_id."
  type        = string
  sensitive   = true
  default     = ""

  validation {
    condition     = var.hf_token == "" || var.hf_token_secret_id == ""
    error_message = "Set either hf_token or hf_token_secret_id, not both."
  }
}

variable "llm_model_name" {
  description = "Foundry model used to enhance the prompt and write the storyboard."
  type        = string
  default     = "gpt-6-astra"
}

variable "llm_model_version" {
  type    = string
  default = "2026-09-03"
}

variable "llm_capacity" {
  description = "GlobalStandard capacity in thousands of tokens per minute."
  type        = number
  default     = 200
}

variable "default_video_model" {
  description = "Video model used when the request doesn't specify one: wan22, ltx2, ltx25 or hunyuan15."
  type        = string
  default     = "wan22"
}

variable "tts_voice" {
  description = "Azure AI Speech neural voice used for the narration."
  type        = string
  default     = "en-US-AndrewMultilingualNeural"
}

variable "education_environment" {
  description = "Optional educational provider configuration. Does not create model deployments. Secrets must use managed identity, not this map."
  type        = map(string)
  default     = {}

  validation {
    condition = alltrue([
      for key in keys(var.education_environment) : contains([
        "EDUCATION_TEXT_MODELS", "EDUCATION_SEARCH_MODEL", "FOUNDRY_IMAGE_ENDPOINT",
        "FOUNDRY_IMAGE_MODEL", "FOUNDRY_VIDEO_ENDPOINT", "FOUNDRY_VIDEO_MODEL",
        "DRAWIO_MCP_URL", "DRAWIO_EXPORT_COMMAND", "COMFY_IMAGE_WORKFLOW", "EDUCATION_FONT"
      ], key)
    ])
    error_message = "Only educational provider environment variables may be supplied."
  }

}

variable "education_drawio_image" {
  description = "Optional pinned self-hosted draw.io MCP image. Runs privately beside the orchestrator on port 3001; set DRAWIO_MCP_URL to http://localhost:3001/mcp. Requires the educational orchestrator image for native export."
  type        = string
  default     = ""

  validation {
    condition     = var.education_drawio_image == "" || (can(regex("(?::[^/:]+|@sha256:[0-9a-f]{64})$", var.education_drawio_image)) && !endswith(var.education_drawio_image, ":latest"))
    error_message = "Use a pinned image tag/digest, not an unversioned image or latest."
  }
}

variable "educational_runtime" {
  description = "Build the opt-in orchestrator image with pinned native draw.io, Xvfb, and fonts. No resources are deployed until Terraform is applied."
  type        = bool
  default     = false
}

variable "voice_clone_enabled" {
  description = "Deploy the serverless GPU voice-clone service (Qwen3-TTS, Chatterbox, OpenVoice v2, Fish Audio S2 Pro) and enable optional voice cloning in the orchestrator."
  type        = bool
  default     = true
}

variable "voice_clone_workload_profile" {
  description = "GPU workload profile of the voice-clone service; it scales to zero when idle. The ComfyUI workers use the whole A100 quota (2), so the default is the T4 profile: engines run in fp16 there. Use GPU-NC24-A100 when A100 quota is available."
  type        = string
  default     = "GPU-NC8as-T4"
}

variable "voice_clone_cpu" {
  description = "Voice-clone container vCPU allocation (T4 profile: up to 8)."
  type        = number
  default     = 4
}

variable "voice_clone_memory_gib" {
  description = "Voice-clone container system RAM in GiB (separate from GPU VRAM; T4 profile: up to 56); engines are loaded one at a time."
  type        = number
  default     = 28
}
