variable "prefix" {
  description = "Short unique suffix used in resource names (lowercase letters and digits)."
  type        = string
  default     = "aivideo570"
}

variable "location" {
  description = "Azure region. Must offer the GPU VM size and the gpt-6-astra GlobalStandard deployment."
  type        = string
  default     = "germanywestcentral"
}

variable "vm_size" {
  description = "GPU VM size hosting ComfyUI. 80+ GB of VRAM is recommended to run the 14B-22B video models at full quality."
  type        = string
  default     = "Standard_NC40ads_H100_v5"
}

variable "vm_spot" {
  description = "Use a Spot VM (cheaper, but can be evicted in the middle of a long video job)."
  type        = bool
  default     = true
}

variable "admin_source_address_prefix" {
  description = "CIDR (or service tag) allowed to SSH into the GPU VM, e.g. 'x.x.x.x/32'. Use an SSH tunnel to reach the ComfyUI UI."
  type        = string
  default     = "*"
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
  default     = 500
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
  description = "Optional educational provider configuration. Does not create model deployments or start the GPU VM. Secrets must use managed identity, not this map."
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
