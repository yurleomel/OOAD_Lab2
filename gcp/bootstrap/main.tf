# One-time setup using the owner's application-default credentials and HCP
# login. Local state stays here, ignored by Git. No service-account key exists.
terraform {
  required_version = ">= 1.10"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    tfe = {
      source  = "hashicorp/tfe"
      version = "~> 0.82"
    }
  }
}

variable "project_id" {
  type = string
}

variable "billing_account_id" {
  type        = string
  description = "Billing account ID (not a payment card); required for the project-scoped $5 alert."
}

variable "organization" {
  type    = string
  default = "ooad-yurleomel"
}

variable "workspace" {
  type    = string
  default = "peach-gcp"
}

variable "cognito_user_pool_id" {
  type = string
}

variable "cognito_client_id" {
  type = string
}

provider "google" {
  project = var.project_id
  region  = "us-central1"
}

provider "tfe" {
  organization = var.organization
}

data "google_project" "main" {
  project_id = var.project_id
  depends_on = [google_project_service.bootstrap]
}

resource "google_project_service" "bootstrap" {
  for_each = toset([
    "billingbudgets.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
  lifecycle {
    prevent_destroy = true
  }
}

# It alerts the billing administrators at 50%, 90% and 100%; it is not a cap.
resource "google_billing_budget" "lab" {
  billing_account = var.billing_account_id
  display_name    = "Peach GCP Lab 9 — USD 5 monthly alert"
  budget_filter {
    projects               = ["projects/${data.google_project.main.number}"]
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
  }
  amount {
    specified_amount {
      currency_code = "USD"
      units         = "5"
    }
  }
  dynamic "threshold_rules" {
    for_each = [0.5, 0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }
  depends_on = [google_project_service.bootstrap]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account" "terraform" {
  account_id   = "peach-terraform"
  display_name = "HCP Terraform — peach-gcp only"
  depends_on   = [google_project_service.bootstrap]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account" "api" {
  account_id   = "peach-api"
  display_name = "Lanora API and migration job"
  depends_on   = [google_project_service.bootstrap]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "terraform" {
  for_each = toset([
    "roles/run.admin",
    "roles/cloudsql.admin",
    "roles/artifactregistry.admin",
    "roles/secretmanager.admin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/firebase.admin",
    "roles/storage.admin",
    "roles/bigquery.admin",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.terraform.email}"
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "api_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account_iam_member" "terraform_api" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.terraform.email}"
  lifecycle {
    prevent_destroy = true
  }
}

resource "tfe_workspace" "gcp" {
  name                  = var.workspace
  organization          = var.organization
  working_directory     = "gcp"
  terraform_version     = "1.17.0"
  auto_apply            = false
  allow_destroy_plan    = false
  execution_mode        = "remote"
  global_remote_state   = false
  file_triggers_enabled = false
  description           = "Lab 9: GCP only, separate from peach-prod. Remote runs with short-lived GCP credentials."
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_iam_workload_identity_pool" "hcp" {
  workload_identity_pool_id = "peach-hcp"
  display_name              = "HCP Terraform for Peach"
  depends_on                = [google_project_service.bootstrap]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_iam_workload_identity_pool_provider" "hcp" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.hcp.workload_identity_pool_id
  workload_identity_pool_provider_id = "terraform"
  attribute_mapping = {
    "google.subject"         = "assertion.sub"
    "attribute.workspace_id" = "assertion.terraform_workspace_id"
  }
  # Immutable workspace ID, not a name someone could register again.
  attribute_condition = "assertion.terraform_workspace_id == '${tfe_workspace.gcp.id}' && assertion.terraform_organization_name == '${var.organization}'"
  oidc {
    issuer_uri        = "https://app.terraform.io"
    allowed_audiences = ["gcp.workload.identity"]
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account_iam_member" "hcp" {
  service_account_id = google_service_account.terraform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.hcp.name}/attribute.workspace_id/${tfe_workspace.gcp.id}"
  lifecycle {
    prevent_destroy = true
  }
}

locals {
  hcp_environment = {
    TFC_GCP_PROVIDER_AUTH              = "true"
    TFC_GCP_WORKLOAD_IDENTITY_AUDIENCE = "gcp.workload.identity"
    TFC_GCP_RUN_SERVICE_ACCOUNT_EMAIL  = google_service_account.terraform.email
    TFC_GCP_PROJECT_NUMBER             = data.google_project.main.number
    TFC_GCP_WORKLOAD_POOL_ID           = google_iam_workload_identity_pool.hcp.workload_identity_pool_id
    TFC_GCP_WORKLOAD_PROVIDER_ID       = google_iam_workload_identity_pool_provider.hcp.workload_identity_pool_provider_id
  }
  hcp_inputs = {
    project_id                    = var.project_id
    runtime_service_account_email = google_service_account.api.email
    cognito_user_pool_id          = var.cognito_user_pool_id
    cognito_client_id             = var.cognito_client_id
  }
}

resource "tfe_variable" "environment" {
  for_each     = local.hcp_environment
  workspace_id = tfe_workspace.gcp.id
  key          = each.key
  value        = each.value
  category     = "env"
  lifecycle {
    prevent_destroy = true
  }
}

resource "tfe_variable" "input" {
  for_each     = local.hcp_inputs
  workspace_id = tfe_workspace.gcp.id
  key          = each.key
  value        = each.value
  category     = "terraform"
  lifecycle {
    prevent_destroy = true
  }
}

output "workspace_url" {
  value = "https://app.terraform.io/app/${var.organization}/workspaces/${var.workspace}"
}

output "runtime_service_account_email" {
  value = google_service_account.api.email
}

# A single batch demo worker, separate from the API and default compute identity.
resource "google_service_account" "dataflow" {
  account_id   = "peach-dataflow"
  display_name = "Lab 9 synthetic batch demo only"
  depends_on   = [google_project_service.bootstrap]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "dataflow" {
  for_each = toset(["roles/dataflow.worker", "roles/bigquery.jobUser"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.dataflow.email}"
  lifecycle {
    prevent_destroy = true
  }
}
