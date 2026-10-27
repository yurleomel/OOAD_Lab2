# The one piece that has to exist before HCP Terraform can do anything: the
# workspace that runs infra/, and the AWS role its runs assume through OIDC.
# Applied from a laptop with the owner's own credentials (AWS profile and
# `terraform login`); its state is a local file, kept out of Git.
#
#   terraform -chdir=infra/bootstrap init
#   terraform -chdir=infra/bootstrap apply
#
# Then `make infra-init` in infra/. github_repo needs the HCP Terraform GitHub
# App installed on the repository (github.com/apps/terraform-cloud, only this
# repository); with it, pull requests get a plan as a check and a merge to
# main applies. Set it to "" to go back to CLI-driven runs.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    tfe = {
      source  = "hashicorp/tfe"
      version = "~> 0.82"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

variable "project_name" {
  type    = string
  default = "peach"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "tfc_organization" {
  type    = string
  default = "ooad-yurleomel"
}

variable "workspace_name" {
  type    = string
  default = "peach-prod"
}

variable "github_repo" {
  type        = string
  default     = "yurleomel/OOAD_Lab2"
  description = "owner/name of the repository whose default branch the workspace follows. Empty: CLI-driven only."
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      PROJECT_NAME = var.project_name
      ManagedBy    = "terraform-bootstrap"
    }
  }
}

# The token comes from `terraform login`.
provider "tfe" {
  organization = var.tfc_organization
}

# --- AWS trusts HCP Terraform's runs ----------------------------------------

data "tls_certificate" "hcp" {
  url = "https://app.terraform.io"
}

resource "aws_iam_openid_connect_provider" "hcp" {
  url             = "https://app.terraform.io"
  client_id_list  = ["aws.workload.identity"]
  thumbprint_list = [data.tls_certificate.hcp.certificates[0].sha1_fingerprint]
}

# Only runs of this one workspace may assume the role - not every workspace of
# the organization, as in the lab's playground.
resource "aws_iam_role" "hcp" {
  name = "hcp-terraform-${var.workspace_name}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.hcp.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "app.terraform.io:aud" = "aws.workload.identity" }
        StringLike = {
          "app.terraform.io:sub" = "organization:${var.tfc_organization}:project:*:workspace:${var.workspace_name}:run_phase:*"
        }
      }
    }]
  })
}

# For the class project. infra/ creates IAM roles and policies, and a role that
# may do that can grant itself anything, so a narrower list buys little here; a
# real team splits plan (read-only) and apply roles instead.
resource "aws_iam_role_policy_attachment" "hcp" {
  role       = aws_iam_role.hcp.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# --- the workspace -----------------------------------------------------------

data "tfe_github_app_installation" "this" {
  count = var.github_repo != "" ? 1 : 0
  name  = split("/", var.github_repo)[0]
}

resource "tfe_workspace" "infra" {
  name              = var.workspace_name
  description       = "Cognito, the weekly report and the agenda parser (infra/)."
  working_directory = "infra"
  terraform_version = "~> 1.17.0"

  # A merge to main applies without a click: the review happened on the plan
  # in the pull request.
  auto_apply = true

  # Only changes to the root module start a run, not the app or this folder.
  trigger_patterns = ["/infra/*.tf", "/infra/*.tfvars", "/infra/.terraform.lock.hcl"]

  dynamic "vcs_repo" {
    for_each = var.github_repo != "" ? [var.github_repo] : []
    content {
      # No branch: the repository's default one, main.
      identifier                 = vcs_repo.value
      github_app_installation_id = data.tfe_github_app_installation.this[0].id
    }
  }
}

# Plan and apply on HCP Terraform's machines, not the laptop.
resource "tfe_workspace_settings" "infra" {
  workspace_id   = tfe_workspace.infra.id
  execution_mode = "remote"
}

# Dynamic credentials: every run trades its signed token for this role's
# temporary keys. No access key is stored anywhere.
resource "tfe_variable" "aws_provider_auth" {
  workspace_id = tfe_workspace.infra.id
  category     = "env"
  key          = "TFC_AWS_PROVIDER_AUTH"
  value        = "true"
}

resource "tfe_variable" "aws_run_role_arn" {
  workspace_id = tfe_workspace.infra.id
  category     = "env"
  key          = "TFC_AWS_RUN_ROLE_ARN"
  value        = aws_iam_role.hcp.arn
}

output "role_arn" {
  value = aws_iam_role.hcp.arn
}

output "workspace_url" {
  value = tfe_workspace.infra.html_url
}
