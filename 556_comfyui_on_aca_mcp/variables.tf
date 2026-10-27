variable "prefix" {
  description = "Prefix for resource names."
  type        = string
  default     = "556a"
}

variable "subscription_id" {
  description = "Explicit deployment subscription; never inferred from the CLI default."
  type        = string
  default     = "2524a5e1-00d7-43c2-a7cf-a87b79df2415"
}

variable "location" {
  description = "Region supporting the serverless A100 workload profile."
  type        = string
  default     = "swedencentral"
}

variable "enable_mcp" {
  description = "Enable only after building the MCP image in ACR."
  type        = bool
  default     = true
}

variable "comfyui_mcp_image_tag" {
  description = "Digest-pinned ComfyUI MCP image built in this demo's ACR."
  type        = string
  default     = "0.0.1"
}
