# GCS raw lake
resource "google_storage_bucket" "raw" {
  name                        = "solana-dex-raw"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 90
    }
  }

  labels = {
    layer   = "bronze"
    project = "solana-dex-analytics"
  }
}

# BigQuery datasets
locals {
  bq_datasets = {
    solana_raw = {
      dataset_id  = "solana_raw"
      description = "Raw normalized tables, snapshot-stamped rows"
    }
    solana_staging = {
      dataset_id  = "solana_staging"
      description = "dbt staging models"
    }
    solana_intermediate = {
      dataset_id  = "solana_intermediate"
      description = "dbt intermediate models"
    }
    solana_marts = {
      dataset_id  = "solana_marts"
      description = "dbt gold layer, star schema, trailing 24h naming"
    }
  }
}

resource "google_bigquery_dataset" "datasets" {
  for_each = local.bq_datasets

  dataset_id  = each.value.dataset_id
  project     = var.project_id
  location    = var.region
  description = each.value.description

  labels = {
    project = "solana-dex-analytics"
  }
}

# Service account
resource "google_service_account" "pipeline" {
  account_id   = "solana-pipeline-sa"
  display_name = "Solana Pipeline Service Account"
  project      = var.project_id
}

# IAM bindings
resource "google_storage_bucket_iam_member" "pipeline_object_admin" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_bigquery_dataset_iam_member" "pipeline_data_editor" {
  for_each = google_bigquery_dataset.datasets

  project    = var.project_id
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_secret_manager_secret_iam_member" "pipeline_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.prefect_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.pipeline.email}"
}

# Artifact Registry
resource "google_artifact_registry_repository" "pipeline" {
  repository_id = "solana-pipeline"
  location      = var.region
  format        = "DOCKER"
  project       = var.project_id

  labels = {
    project = "solana-dex-analytics"
  }
}

# Secret Manager
resource "google_secret_manager_secret" "prefect_api_key" {
  secret_id = "prefect-api-key"
  project   = var.project_id

  replication {
    auto {}
  }
}


# Workload Identity Federation (GitHub Actions
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions-pool"
  project                   = var.project_id
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions OIDC tokens"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  project                            = var.project_id
  display_name                       = "GitHub Actions OIDC Provider"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == \"${var.github_repo}\""
}

resource "google_service_account_iam_member" "github_wif_impersonation" {
  service_account_id = google_service_account.pipeline.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
