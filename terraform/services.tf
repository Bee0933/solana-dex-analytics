# APIs required by the Cloud Run Job + Scheduler (storage/bigquery/etc. enabled already)
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
