locals {
  api_environment = {
    APP_ENV              = "production"
    LOG_LEVEL            = "info"
    DB_POOLING           = "false"
    CORS_ORIGINS         = join(",", local.site_origins)
    COGNITO_REGION       = var.cognito_region
    COGNITO_USER_POOL_ID = var.cognito_user_pool_id
    COGNITO_CLIENT_ID    = var.cognito_client_id
  }
}

resource "google_cloud_run_v2_service" "api" {
  count               = var.api_image == null ? 0 : 1
  name                = "peach-api"
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account                  = var.runtime_service_account_email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    timeout                          = "60s"
    max_instance_request_concurrency = 10
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }
    containers {
      image = var.api_image
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }
      dynamic "env" {
        for_each = local.api_environment
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = google_secret_manager_secret_version.database_url.version
          }
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        period_seconds    = 5
        failure_threshold = 12
      }
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.api_database]
  lifecycle {
    prevent_destroy = true
  }
}

# The browser supplies a Cognito token, not a Google Cloud IAM token. FastAPI
# still checks signature, issuer, audience, expiry and token_use on /api/v1.
resource "google_cloud_run_v2_service_iam_member" "browser" {
  count    = var.api_image == null ? 0 : 1
  location = var.region
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
  lifecycle {
    prevent_destroy = true
  }
}

# Migrations are a one-off job, never a race between autoscaled API instances.
resource "google_cloud_run_v2_job" "migrate" {
  count               = var.api_image == null ? 0 : 1
  name                = "peach-migrate"
  location            = var.region
  deletion_protection = true
  template {
    template {
      service_account = var.runtime_service_account_email
      max_retries     = 0
      timeout         = "300s"
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.main.connection_name]
        }
      }
      containers {
        image   = var.api_image
        command = ["python"]
        args    = ["gcp_migrate.py"]
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
        dynamic "env" {
          for_each = local.api_environment
          content {
            name  = env.key
            value = env.value
          }
        }
        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_url.secret_id
              version = google_secret_manager_secret_version.database_url.version
            }
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.api_database]
  lifecycle {
    prevent_destroy = true
  }
}
