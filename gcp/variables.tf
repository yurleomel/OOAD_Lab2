variable "project_id" {
  type        = string
  description = "Existing, billing-enabled Google Cloud project. Bootstrap uses the same ID."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use a valid GCP project ID, 6-30 lowercase characters."
  }
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "runtime_service_account_email" {
  type        = string
  description = "Dedicated API identity created by gcp/bootstrap, never the default compute identity."
}

variable "database_running" {
  type        = bool
  default     = true
  description = "Keep true for initial provisioning/user creation; false stops compute after the demo, but storage still bills."
}

variable "api_image" {
  type        = string
  default     = null
  nullable    = true
  description = "Immutable Artifact Registry image URL with @sha256 digest; null prepares infrastructure only."
  validation {
    condition     = var.api_image == null ? true : can(regex("^[a-z0-9-]+-docker[.]pkg[.]dev/.+@sha256:[a-f0-9]{64}$", var.api_image))
    error_message = "Build and push the GCP image first, then set its Artifact Registry digest URL."
  }
}

variable "cognito_region" {
  type    = string
  default = "us-east-1"
}

variable "cognito_user_pool_id" {
  type        = string
  description = "Existing AWS Cognito user pool: sign-in stays on AWS in the required lab scope."
  validation {
    condition     = length(var.cognito_user_pool_id) > 0
    error_message = "Production must have a Cognito user pool."
  }
}

variable "cognito_client_id" {
  type = string
  validation {
    condition     = length(var.cognito_client_id) > 0
    error_message = "Production must have a Cognito app client."
  }
}
