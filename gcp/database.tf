resource "google_sql_database_instance" "main" {
  name                = "peach-postgres"
  region              = var.region
  database_version    = "POSTGRES_17"
  deletion_protection = true
  depends_on          = [google_project_service.api]

  settings {
    tier              = "db-f1-micro"
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = 10
    disk_autoresize   = false
    activation_policy = var.database_running ? "ALWAYS" : "NEVER"

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
      # No authorized_networks: connections use the authenticated Cloud SQL
      # proxy socket mounted into Cloud Run, not an open PostgreSQL port.
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = false
      start_time                     = "03:00"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_database" "app" {
  name     = "peach"
  instance = google_sql_database_instance.main.name
  lifecycle {
    prevent_destroy = true
  }
}

resource "random_password" "database" {
  length  = 32
  special = false
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_user" "app" {
  name     = "peach"
  instance = google_sql_database_instance.main.name
  password = random_password.database.result
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "peach-database-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.api]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id
  # The socket path contains no percent escapes: Alembic reads this URL via
  # ConfigParser. The generated password is alphanumeric for the same reason.
  secret_data = "postgresql+asyncpg://${google_sql_user.app.name}:${random_password.database.result}@/${google_sql_database.app.name}?host=/cloudsql/${google_sql_database_instance.main.connection_name}"
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "api_database" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.runtime_service_account_email}"
  lifecycle {
    prevent_destroy = true
  }
}
