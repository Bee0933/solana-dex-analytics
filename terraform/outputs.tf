output "gcs_bucket_name" {
  description = "Name of the raw data GCS bucket"
  value       = google_storage_bucket.raw.name
}

output "bq_dataset_raw" {
  description = "BigQuery raw dataset ID"
  value       = google_bigquery_dataset.datasets["solana_raw"].dataset_id
}

output "bq_dataset_staging" {
  description = "BigQuery staging dataset ID"
  value       = google_bigquery_dataset.datasets["solana_staging"].dataset_id
}

output "bq_dataset_intermediate" {
  description = "BigQuery intermediate dataset ID"
  value       = google_bigquery_dataset.datasets["solana_intermediate"].dataset_id
}

output "bq_dataset_marts" {
  description = "BigQuery marts dataset ID"
  value       = google_bigquery_dataset.datasets["solana_marts"].dataset_id
}

output "service_account_email" {
  description = "Pipeline service account email"
  value       = google_service_account.pipeline.email
}

output "artifact_registry_repo" {
  description = "Artifact Registry Docker repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/solana-pipeline"
}

output "workload_identity_provider" {
  description = "Workload Identity Provider resource name for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "cloud_run_job" {
  description = "Cloud Run Job name"
  value       = google_cloud_run_v2_job.pipeline.name
}

output "scheduler_job" {
  description = "Cloud Scheduler job name"
  value       = google_cloud_scheduler_job.daily.name
}
