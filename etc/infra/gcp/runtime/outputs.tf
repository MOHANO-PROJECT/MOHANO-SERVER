output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "migration_job_name" {
  value = google_cloud_run_v2_job.migrate.name
}
