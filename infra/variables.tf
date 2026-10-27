# Non-secret values go in terraform.tfvars. Secrets and personal addresses are
# sensitive variables set in the HCP Terraform workspace, never in Git.

variable "project_name" {
  type        = string
  default     = "peach"
  description = "Prefix for every name, and the value of every PROJECT_NAME tag."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.project_name))
    error_message = "project_name must be lowercase letters, digits and dashes."
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "local_site_url" {
  type        = string
  default     = "http://localhost:3000"
  description = "Compose's site. Sign-in may return to it, and the parser answers it."
}

# --- sign-in (auth.tf) -------------------------------------------------------

variable "google_client_id" {
  type        = string
  default     = ""
  description = "OAuth client id from Google Cloud. Empty keeps Google off."
}

variable "google_client_secret" {
  type      = string
  default   = ""
  sensitive = true
}

# --- weekly report (reports.tf) ----------------------------------------------

variable "mail_domain" {
  type        = string
  default     = ""
  description = <<-EOT
    Domain the reports are sent from (reports@<domain>). Its SES identity
    prints three DKIM CNAMEs to add at the DNS provider. Empty means no
    identity.
  EOT
}

variable "report_sender_name" {
  type    = string
  default = "Lanora reports"
}

variable "report_sender_address" {
  type        = string
  default     = ""
  sensitive   = true
  description = <<-EOT
    The From address. Empty means reports@<mail_domain>, or, with no domain
    either, no sender: the mailer then logs the report instead of sending it.
    While the domain's DKIM is not verified, a verified address goes here.
  EOT
}

variable "report_recipients" {
  type        = string
  default     = ""
  sensitive   = true
  description = <<-EOT
    Comma-separated addresses. While the account's SES is in the sandbox each
    must be a verified identity too.
  EOT
}

variable "report_schedule" {
  type        = string
  default     = "cron(0 7 ? * MON *)"
  description = "In Europe/Kyiv time. \"rate(5 minutes)\" to watch it fire, then back."
}

variable "report_fail_week" {
  type        = string
  default     = ""
  description = "An ISO week the builder refuses to build, for the dead-letter exercise."
}

variable "report_log_retention_days" {
  type    = number
  default = 7
}

# --- agenda parser (ai.tf) ---------------------------------------------------

variable "parser_api" {
  type        = string
  default     = "converse"
  description = <<-EOT
    converse is AWS's Converse API (bedrock-runtime); messages is the Anthropic
    Messages API on Bedrock (bedrock-mantle), the only way to the Claude 5.x models.
  EOT

  validation {
    condition     = contains(["converse", "messages"], var.parser_api)
    error_message = "parser_api must be converse or messages."
  }
}

variable "parser_model" {
  type        = string
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
  description = "Bedrock model id or inference profile. The lab's: messages + anthropic.claude-opus-5-5."
}

variable "parser_log_retention_days" {
  type    = number
  default = 14
}

variable "budget_email" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Who the monthly budget alarm emails. Empty means no budget."
}

variable "budget_limit_usd" {
  type    = number
  default = 5
}
