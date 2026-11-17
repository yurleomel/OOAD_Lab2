output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend.repository_id}/backend"
}

output "site_url" {
  value = google_firebase_hosting_site.site.default_url
}

output "api_url" {
  value = try(google_cloud_run_v2_service.api[0].uri, null)
}

output "migration_job" {
  value = try(google_cloud_run_v2_job.migrate[0].name, null)
}

output "database_instance" {
  value = google_sql_database_instance.main.name
}

output "database_connection_name" {
  value = google_sql_database_instance.main.connection_name
}
