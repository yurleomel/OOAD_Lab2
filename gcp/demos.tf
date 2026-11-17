# Small retained demo artifacts only. No Dataflow job, VM, Vertex endpoint,
# Composer environment, TTL, automatic cleanup or load generator is provisioned.
resource "google_storage_bucket" "lab9" {
  name                        = "${var.project_id}-lab9"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  depends_on                  = [google_project_service.api]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_storage_bucket_iam_member" "dataflow" {
  bucket = google_storage_bucket.lab9.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:peach-dataflow@${var.project_id}.iam.gserviceaccount.com"
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset" "lab9" {
  dataset_id                 = "lab9"
  location                   = "US"
  description                = "Lab 9 public/synthetic demonstration results; no private application data."
  delete_contents_on_destroy = false
  depends_on                 = [google_project_service.api]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset_iam_member" "dataflow" {
  dataset_id = google_bigquery_dataset.lab9.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:peach-dataflow@${var.project_id}.iam.gserviceaccount.com"
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "top_words" {
  dataset_id          = google_bigquery_dataset.lab9.dataset_id
  table_id            = "shakespeare_top10"
  deletion_protection = true
  schema = jsonencode([
    { name = "corpus", type = "STRING", mode = "NULLABLE" },
    { name = "total_words", type = "INTEGER", mode = "NULLABLE" },
  ])
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "dataflow" {
  dataset_id          = google_bigquery_dataset.lab9.dataset_id
  table_id            = "dataflow_demo"
  deletion_protection = true
  schema = jsonencode([
    { name = "id", type = "INTEGER", mode = "NULLABLE" },
    { name = "topic", type = "STRING", mode = "NULLABLE" },
    { name = "minutes", type = "INTEGER", mode = "NULLABLE" },
  ])
  lifecycle {
    prevent_destroy = true
  }
}
