locals {
  required_services = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "fcm.googleapis.com",
    "firebase.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "sts.googleapis.com",
  ])

  runtime_secret_ids = setunion(
    toset([
      "mohano-database-url-${var.environment}",
      "mohano-jwt-secret-${var.environment}",
      "mohano-r2-access-key-${var.environment}",
      "mohano-r2-secret-key-${var.environment}",
    ]),
    var.environment == "prod" ? toset([]) : toset([
      "mohano-docs-basic-auth-username-${var.environment}",
      "mohano-docs-basic-auth-password-${var.environment}",
    ]),
  )

  # Only the dev runtime stack reads these values during Terraform apply in
  # order to place them directly in the Cloud Run revision YAML. Staging and
  # production retain runtime Secret Manager references instead.
  dev_revision_visible_secret_ids = var.environment == "dev" ? toset([
    "mohano-database-url-${var.environment}",
    "mohano-jwt-secret-${var.environment}",
    "mohano-docs-basic-auth-username-${var.environment}",
    "mohano-docs-basic-auth-password-${var.environment}",
  ]) : toset([])

  artifact_repository_id     = "mohano-api-${var.environment}"
  network_name               = "mohano-private-net-${var.environment}"
  cloud_run_subnet           = "mohano-run-subnet-${var.environment}"
  private_service_ip         = "mohano-private-services-${var.environment}"
  runtime_service_account_id = "mohano-api-${var.environment}"
  github_deployer_account_id = "mohano-github-deploy-${var.environment}"
  github_pool_id             = "mohano-github-${var.environment}"
  github_provider_id         = "mohano-github-actions-${var.environment}"
  github_deployment_branch   = var.environment == "prod" ? "main" : var.environment
  sql_instance_name          = "mohano-mysql-${var.environment}"
  database_name              = "mohano-${var.environment}"
  backups_enabled            = var.environment != "dev"
}

data "google_project" "current" {}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "api" {
  location      = var.region
  repository_id = local.artifact_repository_id
  description   = "Container images for the MOHANO ${var.environment} FastAPI service"
  format        = "DOCKER"

  # CI tags every deploy with a commit SHA. Keep rollback candidates without
  # retaining images forever.
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-recent-20"
    action = "KEEP"
    most_recent_versions {
      keep_count = 20
    }
  }

  cleanup_policies {
    id     = "delete-older-than-60d"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "5184000s"
    }
  }

  depends_on = [google_project_service.required]
}

# Cloud SQL has no public IPv4 address. Cloud Run uses Direct VPC Egress to
# reach its private IP; unlike a Serverless VPC Access connector, this has no
# connector instance that remains billed while idle.
resource "google_compute_network" "private" {
  name                    = local.network_name
  auto_create_subnetworks = false

  depends_on = [google_project_service.required]
}

resource "google_compute_subnetwork" "cloud_run" {
  name          = local.cloud_run_subnet
  region        = var.region
  network       = google_compute_network.private.id
  ip_cidr_range = "10.42.0.0/24"

  private_ip_google_access = true
}

resource "google_compute_global_address" "private_services" {
  name          = local.private_service_ip
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.private.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.private.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]

  depends_on = [google_project_service.required]
}

resource "google_service_account" "runtime" {
  account_id   = local.runtime_service_account_id
  display_name = "MOHANO ${var.environment} Cloud Run runtime"

  depends_on = [google_project_service.required]
}

# GitHub receives short-lived credentials through OIDC. No downloaded service
# account key is ever stored in GitHub Actions secrets.
resource "google_service_account" "github_deployer" {
  account_id   = local.github_deployer_account_id
  display_name = "MOHANO ${var.environment} GitHub Actions deployer"

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = local.github_pool_id
  display_name              = "MOHANO ${var.environment} GitHub Actions"
  description               = "OIDC trust boundary for the MOHANO ${var.environment} server repository"

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = local.github_provider_id
  display_name                       = "MOHANO ${var.environment} GitHub Actions OIDC"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
    "attribute.ref"              = "assertion.ref"
  }

  # Each environment may be deployed only from its corresponding release
  # branch: dev -> dev, staging -> staging, prod -> main.
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/${local.github_deployment_branch}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif" {
  service_account_id = google_service_account.github_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_project_iam_member" "runtime_cloud_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_fcm" {
  project = var.project_id
  role    = "roles/firebasecloudmessaging.admin"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "github_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_project_iam_member" "github_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_service_account_iam_member" "github_runtime_act_as" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_storage_bucket_iam_member" "github_state_access" {
  bucket = var.terraform_state_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_secret_manager_secret" "runtime" {
  for_each = local.runtime_secret_ids

  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "runtime_accessor" {
  for_each = google_secret_manager_secret.runtime

  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# The dev deployer reads only the four intentionally revision-visible values
# while applying the runtime stack. This permission is not granted for staging
# or production, whose revisions use Secret Manager references.
resource "google_secret_manager_secret_iam_member" "github_deployer_dev_revision_accessor" {
  for_each = local.dev_revision_visible_secret_ids

  secret_id = google_secret_manager_secret.runtime[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.github_deployer.email}"
}

# These values are generated once and retained in Terraform state. Keep the
# state bucket private because it contains the generated credentials.
resource "random_password" "cloud_sql_app" {
  length  = 32
  special = false
}

resource "random_password" "jwt" {
  length  = 64
  special = false
}

resource "random_password" "docs_basic_auth" {
  count   = var.environment == "prod" ? 0 : 1
  length  = 10
  special = false
}

# The entry tier is intentionally selected for a low-traffic beta. It has no
# Cloud SQL SLA and must be resized before traffic or connection counts grow.
resource "google_sql_database_instance" "mysql" {
  name                = local.sql_instance_name
  database_version    = "MYSQL_9_7"
  region              = var.region
  deletion_protection = var.deletion_protection

  settings {
    tier              = "db-f1-micro"
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_type         = "PD_HDD"
    disk_size         = 10
    disk_autoresize   = true

    # Direct MySQL access is private-only. Cloud Run connects through Direct
    # VPC Egress and the Cloud SQL connector / Unix socket.
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.private.id
    }

    backup_configuration {
      # Development is disposable; staging and production retain backups.
      enabled = local.backups_enabled
    }
  }

  depends_on = [google_service_networking_connection.private_services]
}

resource "google_sql_database" "mohano" {
  name     = local.database_name
  instance = google_sql_database_instance.mysql.name
}

resource "google_sql_user" "mohano_app" {
  name     = "mohano_app"
  instance = google_sql_database_instance.mysql.name
  host     = "%"
  password = random_password.cloud_sql_app.result

  depends_on = [google_sql_database.mohano]
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.runtime["mohano-database-url-${var.environment}"].id
  secret_data = format(
    "mysql+pymysql://mohano_app:%s@/%s?charset=utf8mb4&unix_socket=/cloudsql/%s",
    urlencode(random_password.cloud_sql_app.result),
    google_sql_database.mohano.name,
    google_sql_database_instance.mysql.connection_name,
  )

  depends_on = [google_sql_user.mohano_app]
}

resource "google_secret_manager_secret_version" "jwt" {
  secret      = google_secret_manager_secret.runtime["mohano-jwt-secret-${var.environment}"].id
  secret_data = random_password.jwt.result
}

resource "google_secret_manager_secret_version" "docs_basic_auth_username" {
  count       = var.environment == "prod" ? 0 : 1
  secret      = google_secret_manager_secret.runtime["mohano-docs-basic-auth-username-${var.environment}"].id
  secret_data = "mohano-admin"
}

resource "google_secret_manager_secret_version" "docs_basic_auth_password" {
  count       = var.environment == "prod" ? 0 : 1
  secret      = google_secret_manager_secret.runtime["mohano-docs-basic-auth-password-${var.environment}"].id
  secret_data = random_password.docs_basic_auth[0].result
}
