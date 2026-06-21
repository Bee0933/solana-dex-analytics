# Read-only service account for Grafana's BigQuery data source.
# The key is generated manually (gcloud iam service-accounts keys create) and
# uploaded to Grafana, so it never lands in Terraform state.
resource "google_service_account" "grafana_bigquery_reader" {
  account_id   = "grafana-bigquery-reader"
  display_name = "Grafana BigQuery Reader"
  project      = var.project_id
}

# read access to the marts dataset only — dashboards query solana_marts
resource "google_bigquery_dataset_iam_member" "grafana_marts_viewer" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.datasets["solana_marts"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.grafana_bigquery_reader.email}"
}

# run query jobs (must be project-level; there is no dataset-scoped jobUser)
resource "google_project_iam_member" "grafana_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.grafana_bigquery_reader.email}"
}
