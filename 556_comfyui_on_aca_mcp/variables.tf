variable "prefix" {
  description = "Prefix for resource names."
  type        = string
  default     = "556"
  validation {
    condition     = can(regex("^[a-z0-9]{3,10}$", var.prefix))
    error_message = "Use 3-10 lowercase letters or digits for globally unique resource names."
  }
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
  default     = false
}

variable "mcp_image" {
  description = "Digest-pinned MCP image built in this demo's ACR."
  type        = string
  default     = ""
  validation {
    condition     = var.mcp_image == "" || can(regex("@sha256:[a-f0-9]{64}$", var.mcp_image))
    error_message = "Use a digest-pinned image, not a mutable tag."
  }
}
