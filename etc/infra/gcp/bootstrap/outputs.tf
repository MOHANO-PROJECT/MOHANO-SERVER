output "artifact_registry_repository" {
  value       = google_artifact_registry_repository.api.id
  description = "Artifact Registry repository resource name."
}

output "artifact_registry_image_prefix" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.api.repository_id}/api"
  description = "Use this prefix when building the FastAPI image."
}

output "cloud_sql_connection_name" {
  value       = google_sql_database_instance.mysql.connection_name
  description = "Cloud Run Unix socket instance connection name."
}

output "cloud_sql_instance_name" {
  value = google_sql_database_instance.mysql.name
}

output "runtime_service_account_email" {
  value = google_service_account.runtime.email
}

output "cloud_run_vpc_network" {
  value       = google_compute_network.private.name
  description = "Pass to the runtime stack as vpc_network."
}

output "cloud_run_vpc_subnetwork" {
  value       = google_compute_subnetwork.cloud_run.name
  description = "Pass to the runtime stack as vpc_subnetwork."
}

output "github_deployer_service_account_email" {
  value       = google_service_account.github_deployer.email
  description = "Deploy workflow should impersonate this account through the dynamically resolved OIDC provider."
}

output "github_workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Environment-specific OIDC provider consumed dynamically by the deploy workflow."
}

output "runtime_secret_ids" {
  value       = keys(google_secret_manager_secret.runtime)
  description = "Runtime Secret Manager IDs. DB URL, JWT, and non-production docs Basic Auth versions are created by Bootstrap; R2 versions remain external until configured."
}

output "docs_basic_auth_password" {
  value       = try(random_password.docs_basic_auth[0].result, null)
  sensitive   = true
  description = "Generated 10-character Swagger Basic Auth password for dev/staging."
}
