# Read-only service account for Grafana's BigQuery data source.
# The key is generated manually (gcloud iam service-accounts keys create) and
# uploaded to Grafana, so it never lands in Terraform state.
resource "google_service_account" "grafana_bigquery_reader" {
  account_id   = "grafana-bigquery-reader"
  display_name = "Grafana BigQuery Reader"
  project      = var.project_id
}

# project-level read access — the analytics dashboards read solana_marts, and the
# pipeline-status board also reads the raw landing tables + INFORMATION_SCHEMA.
# Read-only, so project-wide dataViewer is acceptable for this dashboard SA.
resource "google_project_iam_member" "grafana_data_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.grafana_bigquery_reader.email}"
}

# run query jobs (must be project-level; there is no dataset-scoped jobUser)
resource "google_project_iam_member" "grafana_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.grafana_bigquery_reader.email}"
}
