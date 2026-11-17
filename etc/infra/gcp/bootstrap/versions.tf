terraform {
  required_version = ">= 1.6.0"

  # The bucket is created once with gcloud before the first `terraform init`.
  # Backend values are supplied through `terraform init -backend-config=...`.
  backend "gcs" {}

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
