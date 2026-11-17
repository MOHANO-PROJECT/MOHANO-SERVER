locals {
  api_service_name        = "mohano-api-${var.environment}"
  migration_job_name      = "mohano-migrate-${var.environment}"
  database_secret_id      = "mohano-database-url-${var.environment}"
  jwt_secret_id           = "mohano-jwt-secret-${var.environment}"
  r2_access_key_secret_id = "mohano-r2-access-key-${var.environment}"
  r2_secret_key_secret_id = "mohano-r2-secret-key-${var.environment}"
  docs_username_secret_id = "mohano-docs-basic-auth-username-${var.environment}"
  docs_password_secret_id = "mohano-docs-basic-auth-password-${var.environment}"
  object_storage_bucket   = coalesce(var.r2_bucket, "mohano-storage-${var.environment}")
  # The dev environment deliberately materializes these four values into the
  # Cloud Run revision configuration so the operator can inspect them in the
  # Cloud Run YAML. Staging and production continue to use Secret Manager
  # references at runtime.
  expose_dev_secret_values_in_revision = var.environment == "dev"

  base_environment = {
    MOHANO_ENVIRONMENT                   = var.environment
    MOHANO_DATABASE_POOL_SIZE            = "3"
    MOHANO_DATABASE_MAX_OVERFLOW         = "1"
    MOHANO_DATABASE_POOL_TIMEOUT_SECONDS = "30"
    MOHANO_CORS_ORIGINS_RAW              = var.cors_origins_raw
    MOHANO_CORS_ORIGIN_REGEX             = var.cors_origin_regex
    MOHANO_FCM_ENABLED                   = "true"
    MOHANO_FIREBASE_PROJECT_ID           = var.project_id
    MOHANO_GOOGLE_WEB_CLIENT_ID          = var.google_web_client_id
    MOHANO_APPLE_CLIENT_IDS              = var.apple_client_ids
    MOHANO_APPLE_ANDROID_PACKAGE_ID      = "com.example.mohano"
    MOHANO_LINE_CHANNEL_ID               = var.line_channel_id
    MOHANO_KAKAO_APP_ID                  = var.kakao_app_id
  }

  storage_environment = trimspace(var.r2_endpoint) == "" ? {} : {
    MOHANO_OBJECT_STORAGE_ENDPOINT        = var.r2_endpoint
    MOHANO_OBJECT_STORAGE_PUBLIC_ENDPOINT = var.r2_endpoint
    MOHANO_OBJECT_STORAGE_BUCKET          = local.object_storage_bucket
    MOHANO_OBJECT_STORAGE_REGION          = "auto"
  }

  common_environment = merge(local.base_environment, local.storage_environment)
}

# These data sources are intentionally limited to dev. Their values become
# Terraform state and Cloud Run revision configuration through the `value`
# environment-variable fields below.
data "google_secret_manager_secret_version" "database_url" {
  count = local.expose_dev_secret_values_in_revision ? 1 : 0

  secret  = local.database_secret_id
  version = "latest"
}

data "google_secret_manager_secret_version" "jwt" {
  count = local.expose_dev_secret_values_in_revision ? 1 : 0

  secret  = local.jwt_secret_id
  version = "latest"
}

data "google_secret_manager_secret_version" "docs_basic_auth_username" {
  count = local.expose_dev_secret_values_in_revision ? 1 : 0

  secret  = local.docs_username_secret_id
  version = "latest"
}

data "google_secret_manager_secret_version" "docs_basic_auth_password" {
  count = local.expose_dev_secret_values_in_revision ? 1 : 0

  secret  = local.docs_password_secret_id
  version = "latest"
}

resource "google_cloud_run_v2_job" "migrate" {
  name                = local.migration_job_name
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = var.runtime_service_account_email
      timeout         = "600s"
      max_retries     = 1

      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = var.vpc_network
          subnetwork = var.vpc_subnetwork
        }
      }

      containers {
        image   = var.container_image
        command = ["alembic"]
        args    = ["upgrade", "head"]

        dynamic "env" {
          for_each = local.common_environment
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = local.expose_dev_secret_values_in_revision ? [1] : []
          content {
            name  = "MOHANO_DATABASE_URL"
            value = data.google_secret_manager_secret_version.database_url[0].secret_data
          }
        }

        dynamic "env" {
          for_each = local.expose_dev_secret_values_in_revision ? [] : [1]
          content {
            name = "MOHANO_DATABASE_URL"
            value_source {
              secret_key_ref {
                secret  = local.database_secret_id
                version = "latest"
              }
            }
          }
        }

        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [var.cloud_sql_connection_name]
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service" "api" {
  name                 = local.api_service_name
  location             = var.region
  invoker_iam_disabled = true

  template {
    service_account                  = var.runtime_service_account_email
    timeout                          = "60s"
    max_instance_request_concurrency = 20

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = var.vpc_network
        subnetwork = var.vpc_subnetwork
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      dynamic "env" {
        for_each = local.common_environment
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.expose_dev_secret_values_in_revision ? [1] : []
        content {
          name  = "MOHANO_DATABASE_URL"
          value = data.google_secret_manager_secret_version.database_url[0].secret_data
        }
      }

      dynamic "env" {
        for_each = local.expose_dev_secret_values_in_revision ? [] : [1]
        content {
          name = "MOHANO_DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = local.database_secret_id
              version = "latest"
            }
          }
        }
      }

      dynamic "env" {
        for_each = local.expose_dev_secret_values_in_revision ? [1] : []
        content {
          name  = "MOHANO_JWT_SECRET_KEY"
          value = data.google_secret_manager_secret_version.jwt[0].secret_data
        }
      }

      dynamic "env" {
        for_each = local.expose_dev_secret_values_in_revision ? [] : [1]
        content {
          name = "MOHANO_JWT_SECRET_KEY"
          value_source {
            secret_key_ref {
              secret  = local.jwt_secret_id
              version = "latest"
            }
          }
        }
      }

      dynamic "env" {
        for_each = trimspace(var.r2_endpoint) == "" ? [] : [1]
        content {
          name = "MOHANO_OBJECT_STORAGE_ACCESS_KEY"
          value_source {
            secret_key_ref {
              secret  = local.r2_access_key_secret_id
              version = "latest"
            }
          }
        }
      }

      dynamic "env" {
        for_each = trimspace(var.r2_endpoint) == "" ? [] : [1]
        content {
          name = "MOHANO_OBJECT_STORAGE_SECRET_KEY"
          value_source {
            secret_key_ref {
              secret  = local.r2_secret_key_secret_id
              version = "latest"
            }
          }
        }
      }

      dynamic "env" {
        for_each = local.expose_dev_secret_values_in_revision ? [1] : []
        content {
          name  = "MOHANO_DOCS_BASIC_AUTH_USERNAME"
          value = data.google_secret_manager_secret_version.docs_basic_auth_username[0].secret_data
        }
      }

      dynamic "env" {
        for_each = local.expose_dev_secret_values_in_revision ? [1] : []
        content {
          name  = "MOHANO_DOCS_BASIC_AUTH_PASSWORD"
          value = data.google_secret_manager_secret_version.docs_basic_auth_password[0].secret_data
        }
      }

      dynamic "env" {
        for_each = var.environment == "staging" ? [1] : []
        content {
          name = "MOHANO_DOCS_BASIC_AUTH_USERNAME"
          value_source {
            secret_key_ref {
              secret  = local.docs_username_secret_id
              version = "latest"
            }
          }
        }
      }

      dynamic "env" {
        for_each = var.environment == "staging" ? [1] : []
        content {
          name = "MOHANO_DOCS_BASIC_AUTH_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = local.docs_password_secret_id
              version = "latest"
            }
          }
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [var.cloud_sql_connection_name]
      }
    }
  }
}

# MOHANO authenticates API requests itself. The Cloud Run Invoker IAM check is
# disabled because Android/iOS clients cannot present Google IAM credentials.
# Every private resource remains protected by the FastAPI JWT authorization
# layer. This avoids granting the special `allUsers` principal, which can be
# blocked by an organization-level domain restriction policy.
