locals {
  apis = toset([
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
    "logging.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
    "bigquery.googleapis.com",
    "dataflow.googleapis.com",
    "compute.googleapis.com",
    "aiplatform.googleapis.com",
    "vision.googleapis.com",
    "storage.googleapis.com",
  ])
  site_origins = [
    "https://${var.project_id}.web.app",
    "https://${var.project_id}.firebaseapp.com",
  ]
}

resource "google_project_service" "api" {
  for_each           = setsubtract(local.apis, toset(["cloudresourcemanager.googleapis.com"]))
  service            = each.value
  disable_on_destroy = false
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = "peach"
  format        = "DOCKER"
  description   = "Lanora Cloud Run images; no automatic deletion policies."
  depends_on    = [google_project_service.api]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_firebase_project" "site" {
  provider   = google-beta
  project    = var.project_id
  depends_on = [google_project_service.api]
  # deletion_policy = "PREVENT" is available in a newer provider; v7 uses
  # lifecycle.prevent_destroy below. Firebase itself cannot be removed.
  lifecycle {
    prevent_destroy = true
  }
}

# Use the default Firebase site (the project ID), and adopt it if Firebase
# has already provisioned it while adding Firebase to the project.
resource "google_firebase_hosting_site" "site" {
  provider        = google-beta
  project         = google_firebase_project.site.project
  site_id         = var.project_id
  deletion_policy = "PREVENT"
  lifecycle {
    prevent_destroy = true
  }
}
