variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region for all resources"
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Deployment environment"

  validation {
    condition     = contains(["local", "staging", "prod"], var.environment)
    error_message = "environment must be one of: local, staging, prod."
  }
}

variable "github_repo" {
  type        = string
  description = "GitHub repository in org/repo format — used for Workload Identity Federation"
}

variable "prefect_api_url" {
  type        = string
  description = "Prefect Cloud API base URL"
  default     = "https://api.prefect.cloud/api"
}

variable "notification_email" {
  type        = string
  description = "Email address for pipeline failure alerts"
}
