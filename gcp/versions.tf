terraform {
  required_version = ">= 1.10"

  cloud {
    organization = "ooad-yurleomel"
    workspaces {
      name = "peach-gcp"
    }
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  default_labels = {
    project    = "peach"
    managed_by = "terraform"
    lab        = "9"
  }
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
}
