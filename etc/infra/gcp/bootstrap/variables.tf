variable "project_id" {
  description = "Google Cloud project ID that owns MOHANO."
  type        = string
}

variable "environment" {
  description = "Deployment environment used in resource names and secret IDs."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "region" {
  description = "Keep Cloud Run and Cloud SQL in the same region to avoid latency and inter-region charges."
  type        = string
  default     = "asia-northeast1"
}

variable "deletion_protection" {
  description = "Keep true for any environment containing real user data."
  type        = bool
  default     = true
}

variable "terraform_state_bucket" {
  description = "Existing GCS bucket used only for Terraform state. It is created before Terraform initialization."
  type        = string
  default     = "mohano-terraform-state"
}

variable "github_repository" {
  description = "Exact GitHub owner/repository allowed to deploy through Workload Identity Federation."
  type        = string
  default     = "MOHANO-PROJECT/MOHANO-SERVER"
}
