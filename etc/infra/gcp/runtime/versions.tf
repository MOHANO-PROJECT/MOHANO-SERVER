terraform {
  required_version = ">= 1.6.0"

  # Shared remote state lets the GitHub Actions deploy workflow update only
  # the runtime stack. The bootstrap stack uses a different state prefix.
  backend "gcs" {}

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
