# Service account used by the Terraform CI workflow to apply infra changes.
# It needs broad rights (it manages everything), so it's separate from the
# least-privilege runtime pipeline SA.
resource "google_service_account" "terraform" {
  account_id   = "terraform-deployer-sa"
  display_name = "Terraform Deployer (CI)"
  project      = var.project_id
}

# editor covers most resources; the roles below cover what editor can't —
# managing service accounts, project IAM bindings, workload identity pools, and
# BigQuery dataset IAM (dataset ACLs need bigquery.datasets.update).
resource "google_project_iam_member" "terraform_roles" {
  for_each = toset([
    "roles/editor",
    "roles/iam.serviceAccountAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/bigquery.admin",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.terraform.email}"
}

# read/write the Terraform state in the GCS backend bucket
resource "google_storage_bucket_iam_member" "terraform_state" {
  bucket = "${var.project_id}-tf-state"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.terraform.email}"
}

# let GitHub Actions (this repo) impersonate the deployer SA via WIF
resource "google_service_account_iam_member" "terraform_wif_impersonation" {
  service_account_id = google_service_account.terraform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
