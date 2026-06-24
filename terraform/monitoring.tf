# Count ERROR+ log entries from the pipeline + freshness Cloud Run Jobs.
resource "google_logging_metric" "pipeline_errors" {
  name    = "solana-pipeline-errors"
  project = var.project_id
  filter  = <<-EOT
    resource.type="cloud_run_job"
    (resource.labels.job_name="solana-daily" OR resource.labels.job_name="solana-freshness")
    severity>=ERROR
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }

  depends_on = [google_project_service.services]
}

# Email channel for alerts (notification_email variable already exists).
resource "google_monitoring_notification_channel" "email" {
  project      = var.project_id
  display_name = "Solana Pipeline Alerts"
  type         = "email"

  labels = {
    email_address = var.notification_email
  }

  depends_on = [google_project_service.services]
}

# Fire when any ERROR is logged in a 1-hour window.
resource "google_monitoring_alert_policy" "pipeline_errors" {
  project      = var.project_id
  display_name = "Solana pipeline errors"
  combiner     = "OR"

  conditions {
    display_name = "ERROR logs from Cloud Run jobs"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_job\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.pipeline_errors.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  depends_on = [google_project_service.services]
}
