terraform {
  required_version = ">= 1.10"

  # State, locking and runs live in HCP Terraform. The workspace runs plan and
  # apply on its own machines with short-lived AWS credentials (infra/bootstrap),
  # so nobody needs AWS keys to change what is in this folder.
  cloud {
    organization = "ooad-yurleomel"

    workspaces {
      name = "peach-prod"
    }
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      PROJECT_NAME = var.project_name
    }
  }
}
