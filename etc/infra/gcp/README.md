# GCP environment infrastructure

MOHANO uses the same two Terraform stacks for `dev`, `staging`, and `prod`.
The environment is included in every resource name and in the remote-state
prefix so environments can coexist in one Google Cloud project.

```text
Flutter app
   │ HTTPS
   ▼
Cloud Run (FastAPI container, 0–1 instances per environment)
   ├── Cloud SQL Auth Proxy / Unix socket ──► Cloud SQL for MySQL
   ├── runtime service account ─────────────► FCM HTTP v1
   └── short-lived S3 signed URLs ──────────► Cloudflare R2
```

Cloud Run terminates HTTPS, so this architecture does **not** use Caddy or a
public VM. Cloud SQL is intentionally the only always-running GCP workload.
Cloudflare R2 remains the private photo object store; neither its access key
nor its secret is committed to this repository or written to Terraform state.

## Prerequisites

- A billing-enabled Google Cloud project. The current project is
  `mohano-512515`.
- Google Cloud CLI authenticated for that project and Terraform `>= 1.6`.
- A Cloudflare R2 bucket named `mohano-storage-{environment}` and an S3
  API token restricted to that environment's bucket.
- The Firebase Android application already registered in the same GCP project.

Do not use the local `.env`, local Silo credentials, Firebase ADC JSON, or the
local MySQL password in production.

## 1. Create the foundation

Terraform state needs a remote bucket before Terraform itself can initialize.
Create it once. Bootstrap state contains generated application credentials and
the dev runtime state intentionally contains the four dev revision-visible
values described below, so keep this bucket private.

```powershell
gcloud storage buckets create gs://mohano-terraform-state `
  --project=mohano-512515 `
  --location=asia-northeast1 `
  --uniform-bucket-level-access
gcloud storage buckets update gs://mohano-terraform-state --versioning
```

Copy the example and review the environment, identifiers, and region.
`terraform.tfvars` is ignored by Git.

```powershell
Set-Location C:\repository\MOHANO-SERVER\etc\infra\gcp\bootstrap
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init -backend-config="bucket=mohano-terraform-state" -backend-config="prefix=mohano/dev/bootstrap"
terraform plan
terraform apply
```

This enables the required APIs and creates:

- Artifact Registry repository `mohano-api-dev`
- Cloud Run runtime service account, with Cloud SQL client, Secret Manager
  accessor, and Firebase Cloud Messaging permissions
- four **empty** Secret Manager secret containers
- one Tokyo (`asia-northeast1`) Cloud SQL MySQL 9.7 instance, database
  `mohano-dev`, 10 GB HDD, backups disabled for development, no HA, and the
  smallest `db-f1-micro` tier.
- a private VPC, Private Service Access range, and Direct VPC Egress subnet;
  Cloud SQL does not receive a public IPv4 address.

`db-f1-micro` is suitable only for low-traffic beta use and has no Cloud SQL
SLA. Resize it before connection saturation or sustained traffic occurs.

Keep `deletion_protection = true` once any real user exists. Destroying the
bootstrap stack is not a normal deployment operation.

## 2. Bootstrap-managed application credentials

The Bootstrap Terraform stack creates the application-only Cloud SQL user
`mohano_app`, generates its password, and creates the first versions of the
following Secret Manager secrets. The same pattern applies to `staging` and
`prod`.

| Secret ID | Value |
| --- | --- |
| `mohano-jwt-secret-{environment}` | Generated 64-character JWT signing secret. |
| `mohano-database-url-{environment}` | Generated SQLAlchemy URL using the Cloud SQL Unix socket. |

The generated password and JWT secret are stored in Terraform state as
sensitive values. Keep the state bucket private and restrict its IAM access.
Do not put them in `terraform.tfvars`, GitHub Variables, or source control.

The two R2 secret versions remain absent until Cloudflare is configured:
`mohano-r2-access-key-{environment}` and `mohano-r2-secret-key-{environment}`.

## 3. Build and push the FastAPI image

Use a meaningful immutable tag such as the release date or commit SHA.

```powershell
Set-Location C:\repository\MOHANO-SERVER
$image = "asia-northeast1-docker.pkg.dev/mohano-512515/mohano-api-dev/api:2026-11-12-01"
gcloud builds submit --project=mohano-512515 --tag $image .
```

The image includes the Alembic files so Cloud Run Job can apply migrations.

## 4. Deploy the Cloud Run service and migration job

Copy `runtime/terraform.tfvars.example` to `runtime/terraform.tfvars`, replace
the image, Cloud SQL connection name, runtime service-account email, OAuth
identifiers, and the exact public web origin. For `dev`, leave `r2_endpoint`
empty until Cloudflare is configured. Do not use the local-host CORS regex in
production.

```powershell
Set-Location C:\repository\MOHANO-SERVER\etc\infra\gcp\runtime
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init -backend-config="bucket=mohano-terraform-state" -backend-config="prefix=mohano/dev/runtime"
terraform plan
terraform apply
```

The service is public at the Cloud Run edge because Android/iOS clients cannot
present Google IAM credentials. Terraform sets `invoker_iam_disabled = true`
instead of granting the special `allUsers` IAM principal; this also works when
the project is subject to a domain-restricted sharing organization policy.
MOHANO's own FastAPI JWT remains mandatory for all private API resources.

Swagger UI is available at `/v1/docs` in dev and staging behind HTTP Basic Auth.
Bootstrap generates the `mohano-admin` password (10 alphanumeric characters) and
stores it in Secret Manager. For the requested development inspection workflow,
the dev runtime stack reads the DB URL, JWT, Swagger username, and Swagger
password from Secret Manager and writes them as ordinary environment-variable
values in the Cloud Run service revision; the migration job receives the same
plain DB URL. Staging continues to use `secretKeyRef` and production does not
register the documentation routes at all. The dev deployer is granted Secret
Accessor and Secret Manager Viewer only for those four values. Retrieve a
non-production password from the selected Bootstrap state with
`terraform output -raw docs_basic_auth_password` or directly from Secret
Manager when needed:

```powershell
gcloud secrets versions access latest `
  --secret=mohano-docs-basic-auth-password-dev `
  --project=mohano-512515
```

Run migrations once after the job is deployed:

```powershell
gcloud run jobs execute mohano-migrate-dev `
  --project=mohano-512515 `
  --region=asia-northeast1 `
  --wait
```

For future releases: push a new immutable image, update
`container_image`, apply the runtime stack, execute the migration job, then
verify the deployed revision with `GET <api-url>/v1/health`. For a migration
that is not backward compatible, deploy and execute a migration-job-only
revision before moving Cloud Run traffic; do not run destructive schema changes
against a live application without a rollback and backup plan.

## 5. Connect the clients and R2

Use the `api_url` Terraform output as Flutter's production
`MOHANO_API_BASE_URL`, with `/v1` appended. Update OAuth provider return URLs
and allowed origins to the exact public API/web addresses before release.

In Cloudflare R2, set bucket CORS to allow the actual Flutter Web origin for
`GET`, `PUT`, `HEAD`, and the `Content-Type` header. Native Android/iOS uploads
do not use browser CORS, but web uploads do.

## 6. GitHub Actions CI/CD

The repository follows the `badara-server` pattern: GitHub Actions obtains a
short-lived Google credential through Workload Identity Federation (WIF), builds
an image tagged with the commit SHA, updates the Cloud Run migration job, runs
Alembic, and only then moves the API service to that image. No Google service
account JSON key is used or stored in GitHub.

The deployment workflow is `.github/workflows/deploy.yml`:

- Push to `dev` deploys to `dev` automatically.
- Push to `staging` deploys to `staging` automatically.
- Push to `main` deploys to `prod` automatically.
- `prod` should be protected by a required reviewer in the GitHub `prod`
  Environment. The workflow's first gated job uses that Environment, so
  approval happens before verification, Bootstrap, image build, migration, or
  API deployment begins.
- Pull requests never receive Google credentials and cannot deploy.

Each deployment runs Bootstrap `plan/apply` before it reads the generated
outputs, builds the image, migrates the database, and deploys the API. This
reconciles infrastructure changes automatically and removes the need for a
separate manual Bootstrap workflow. It still requires a one-time, out-of-band
Bootstrap WIF provider and administrator service account because the normal
deploy WIF resources are themselves created by Bootstrap.

Create GitHub Environments named `dev`, `staging`, and `prod`. Put the following
Actions **Variables** in each environment. The values are environment-specific
unless noted otherwise:

The two `GCP_BOOTSTRAP_*` variables are shared seed-identity values. Store them
as repository-level Actions Variables so the integrated Bootstrap job can use
the same administrator identity for each environment.

| GitHub Actions variable | Source |
| --- | --- |
| `GCP_PROJECT_ID` | `mohano-512515` |
| `GCP_REGION` | `asia-northeast1` |
| `GCP_TERRAFORM_STATE_BUCKET` | `mohano-terraform-state` |
| `GCP_BOOTSTRAP_WORKLOAD_IDENTITY_PROVIDER` | One-time Bootstrap WIF provider created outside this Terraform stack |
| `GCP_BOOTSTRAP_SERVICE_ACCOUNT` | One-time Bootstrap administrator service account created outside this Terraform stack |
| `MOHANO_R2_ENDPOINT` | `https://<Cloudflare-account-id>.r2.cloudflarestorage.com` (optional for `dev`) |
| `MOHANO_CORS_ORIGINS_RAW` | Exact public web origin; empty when no web client is exposed |
| `MOHANO_CORS_ORIGIN_REGEX` | Empty in staging/production unless explicitly required |
| `MOHANO_GOOGLE_WEB_CLIENT_ID` | Existing Google OAuth Web client ID |
| `MOHANO_APPLE_CLIENT_IDS` | `com.example.mohano,com.example.mohano.web` unless changed |
| `MOHANO_LINE_CHANNEL_ID` | Existing LINE Login channel ID |
| `MOHANO_KAKAO_APP_ID` | Existing Kakao app ID |

These are configuration identifiers, not passwords. Secret Manager remains the
source of truth for the database URL, JWT secret, and R2 credentials. The dev
runtime intentionally copies the database URL, JWT, and Swagger Basic Auth pair
into its Cloud Run revision YAML; staging and prod retain Secret Manager
references. The WIF provider for each environment accepts only its corresponding
branch: `dev` for dev, `staging` for staging, and `main` for prod. The one-time
Bootstrap WIF provider must accept all three branches so that its integrated
Bootstrap job can run:

```powershell
gcloud iam workload-identity-pools providers update-oidc mohano-bootstrap-actions `
  --project=mohano-512515 `
  --location=global `
  --workload-identity-pool=mohano-bootstrap-github `
  --attribute-condition="assertion.repository == 'MOHANO-PROJECT/MOHANO-SERVER' && (assertion.ref == 'refs/heads/dev' || assertion.ref == 'refs/heads/staging' || assertion.ref == 'refs/heads/main')"
```

The deploy workflow first authenticates with the fixed Bootstrap WIF identity,
reads the selected environment's Bootstrap Terraform state, and passes the
generated Workload Identity Provider, deployer service account, Cloud SQL
connection name, runtime service account, VPC network, and subnet to the deploy
job. `GCP_WORKLOAD_IDENTITY_PROVIDER` and
`GCP_GITHUB_DEPLOYER_SERVICE_ACCOUNT` are therefore not GitHub Variables.
The environment-specific R2 bucket is derived by Terraform as
`mohano-storage-{environment}`.

R2 is optional for `dev` while the infrastructure is being validated. Leave
`MOHANO_R2_ENDPOINT` empty or remove it from the `dev` Environment and do not
create R2 secret versions yet. The Cloud Run service will run without object
storage configuration; profile photo APIs remain unavailable until R2 is added.
`staging` and `prod` require the endpoint and R2 secret versions.

Workflow behavior:

- Pull requests and `dev`/`staging`/`main` pushes run Python compile/tests and Terraform format
  checks through `.github/workflows/ci.yml`.
- The deploy job builds an immutable SHA-tagged image in the environment's
  Artifact Registry repository.
- It applies only the migration-job image first, runs `alembic upgrade head`,
  then applies the API service revision and checks `/v1/health`.
- Artifact Registry keeps the newest 20 images and deletes images older than 60
  days, preserving practical rollback capacity while limiting storage growth.

## Cost and operating boundaries

- Cloud Run has `min_instance_count = 0`; it scales to zero between requests.
- Cloud SQL `db-f1-micro` is always billed while provisioned. It is the main
  recurring GCP cost in this design.
- Cloud Run is capped at one instance per environment and the process maintains at most four
  pooled DB connections, bounding this development configuration to one
  instance's normal pool before short-lived overflow/retry behavior.
- Automatic backups are intentionally disabled for development. Enable a backup
  retention policy and configure alerts for Cloud SQL spend, storage growth,
  Cloud Run error rate, and Secret Manager access anomalies before inviting
  external users.

Terraform creates infrastructure only; it does not create secret values, run
migrations outside the CI job, change DNS, configure Cloudflare R2 CORS, or
alter OAuth provider portals.

### Environment naming

Set `environment` to exactly one of `dev`, `staging`, or `prod`. Resource names
then use the following pattern:

```text
mohano-api-dev
mohano-api-staging
mohano-api-prod
```

The same suffix is used for Cloud SQL, Artifact Registry, VPC/subnet, service
accounts, Workload Identity resources, Secret Manager IDs, Cloud Run Jobs, and
the default R2 bucket name. Use state prefixes `mohano/{environment}/bootstrap`
and `mohano/{environment}/runtime`.

The Terraform state bucket and Google Cloud API enablement are project-level
shared resources, so they intentionally do not receive an environment suffix.
