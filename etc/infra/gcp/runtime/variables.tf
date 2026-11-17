variable "project_id" {
  type = string
}

variable "environment" {
  description = "Deployment environment used in resource names, secrets, and runtime configuration."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "region" {
  type    = string
  default = "asia-northeast1"
}

variable "container_image" {
  description = "Immutable Artifact Registry image URI, preferably with a commit/tag rather than latest."
  type        = string
}

variable "cloud_sql_connection_name" {
  description = "Value output by the bootstrap Terraform stack."
  type        = string
}

variable "runtime_service_account_email" {
  description = "Value output by the bootstrap Terraform stack."
  type        = string
}

variable "vpc_network" {
  description = "Private VPC name output by the bootstrap Terraform stack."
  type        = string
}

variable "vpc_subnetwork" {
  description = "Direct VPC Egress subnet output by the bootstrap Terraform stack."
  type        = string
}

variable "r2_endpoint" {
  description = "Cloudflare R2 S3 endpoint. Optional for dev; required for staging and prod."
  type        = string
  default     = ""

  validation {
    condition     = var.environment == "dev" || trimspace(var.r2_endpoint) != ""
    error_message = "r2_endpoint is required for staging and prod."
  }
}

variable "r2_bucket" {
  description = "Environment-specific Cloudflare R2 bucket. Leave null to use mohano-storage-{environment}."
  type        = string
  default     = null
}

variable "cors_origins_raw" {
  description = "Comma-separated, exact public web origins. Native apps do not need an origin here."
  type        = string
  default     = ""
}

variable "cors_origin_regex" {
  description = "Leave empty in production unless a controlled regex is required."
  type        = string
  default     = ""
}

variable "google_web_client_id" {
  type = string
}

variable "apple_client_ids" {
  type    = string
  default = "com.example.mohano,com.example.mohano.web"
}

variable "line_channel_id" {
  type = string
}

variable "kakao_app_id" {
  type = string
}
