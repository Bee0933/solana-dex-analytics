locals {
  # image the job runs; CI updates it to a per-commit tag after each build
  image = "${var.region}-docker.pkg.dev/${var.project_id}/solana-pipeline/solana-pipeline:latest"
}

# Cloud Run Job — runs the daily pipeline container once per invocation
resource "google_cloud_run_v2_job" "pipeline" {
  name     = "solana-daily"
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.pipeline.email
      timeout         = "1800s"
      max_retries     = 1 # rerun the whole job once on failure (loads are idempotent)

      containers {
        image = local.image

        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "GCP_REGION"
          value = var.region
        }
        env {
          name  = "GCS_BUCKET_NAME"
          value = google_storage_bucket.raw.name
        }
        env {
          name  = "BQ_DATASET_RAW"
          value = "solana_raw"
        }
        env {
          name  = "BQ_DATASET_STAGING"
          value = "solana_staging"
        }
        env {
          name  = "BQ_DATASET_INTERMEDIATE"
          value = "solana_intermediate"
        }
        env {
          name  = "BQ_DATASET_MARTS"
          value = "solana_marts"
        }
        env {
          name  = "ENVIRONMENT"
          value = "prod"
        }
        env {
          name  = "LOG_LEVEL"
          value = "INFO"
        }
      }
    }
  }

  depends_on = [google_project_service.services]

  # CI updates the image to a per-commit tag on each deploy; don't let Terraform revert it
  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image]
  }
}

# Cloud Scheduler — triggers the job daily at 2AM UTC via the Cloud Run Admin API
resource "google_cloud_scheduler_job" "daily" {
  name      = "solana-daily-trigger"
  project   = var.project_id
  region    = var.region
  schedule  = "0 2 * * *"
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.pipeline.name}:run"

    oauth_token {
      service_account_email = google_service_account.pipeline.email
    }
  }

  depends_on = [google_project_service.services]
}

# --- IAM for the pipeline SA (reused for both running the job and CI/CD) ---

# run the job (Scheduler) + deploy new revisions (CI). run.developer covers both.
resource "google_project_iam_member" "pipeline_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# push images to Artifact Registry (CI)
resource "google_artifact_registry_repository_iam_member" "pipeline_ar_writer" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.pipeline.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

# allow the SA to deploy a job that runs as itself (CI)
resource "google_service_account_iam_member" "pipeline_act_as_self" {
  service_account_id = google_service_account.pipeline.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.pipeline.email}"
}
