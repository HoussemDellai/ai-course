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
