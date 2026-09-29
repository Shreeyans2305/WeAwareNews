terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# 1. GCS Storage: Video Assets & Clip Runs
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "video_assets" {
  name                        = "weaware-video-assets-${var.project_id}"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true

  # 14-day lifecycle rule on raw clips (runs/*/clips/)
  lifecycle_rule {
    condition {
      age                   = 14
      matches_prefix        = ["runs/"]
    }
    action {
      type = "Delete"
    }
  }
}

# ---------------------------------------------------------------------------
# 2. Service Accounts
# ---------------------------------------------------------------------------

# Video Service Account (runs API & Job)
resource "google_service_account" "video_sa" {
  account_id   = "weaware-video-sa"
  display_name = "WeAware Video Pipeline & API Service Account"
}

# Workflows Service Account
resource "google_service_account" "workflows_sa" {
  account_id   = "weaware-workflows-sa"
  display_name = "WeAware Video Workflows Orchestration Service Account"
}

# Scheduler Service Account
resource "google_service_account" "scheduler_sa" {
  account_id   = "weaware-scheduler-sa"
  display_name = "WeAware Video Scheduler Service Account"
}

# ---------------------------------------------------------------------------
# 3. Least-Privilege IAM Bindings
# ---------------------------------------------------------------------------

# Video SA: Vertex AI access
resource "google_project_iam_member" "video_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.video_sa.email}"
}

# Video SA: Cloud SQL client for database access
resource "google_project_iam_member" "video_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.video_sa.email}"
}

# Video SA: Scoped strictly to the new video GCS bucket
resource "google_storage_bucket_iam_member" "video_bucket_admin" {
  bucket = google_storage_bucket.video_assets.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.video_sa.email}"
}

# Video SA: Token Creator on itself for generating v4 signed URLs
resource "google_service_account_iam_member" "video_token_creator" {
  service_account_id = google_service_account.video_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.video_sa.email}"
}

# Video SA: Secret Manager Accessor for api-key
resource "google_secret_manager_secret_iam_member" "video_api_key_access" {
  project   = var.project_id
  secret_id = "api-key"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.video_sa.email}"
}

# Video SA: Secret Manager Accessor for db-password
resource "google_secret_manager_secret_iam_member" "video_db_pass_access" {
  project   = var.project_id
  secret_id = "db-password"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.video_sa.email}"
}

# New Secret: video-hmac-secret
resource "google_secret_manager_secret" "video_hmac_secret" {
  secret_id = "video-hmac-secret"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "video_hmac_access" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.video_hmac_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.video_sa.email}"
}

# New Secret: video-webhook-url
resource "google_secret_manager_secret" "video_webhook_url" {
  secret_id = "video-webhook-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "video_webhook_access" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.video_webhook_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.video_sa.email}"
}

# Workflows SA: Cloud Build viewer for guard checks
resource "google_project_iam_member" "workflows_build_viewer" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.viewer"
  member  = "serviceAccount:${google_service_account.workflows_sa.email}"
}

# Workflows SA: Secret Manager Accessor for api-key (to call /debug/stats in guard)
resource "google_secret_manager_secret_iam_member" "workflows_api_key_access" {
  project   = var.project_id
  secret_id = "api-key"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workflows_sa.email}"
}

# Workflows SA: Scoped strictly to the specific Cloud Run Job (not project-wide)
resource "google_cloud_run_v2_job_iam_member" "workflows_job_developer" {
  location = var.region
  name     = google_cloud_run_v2_job.video_job.name
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.workflows_sa.email}"
}

# Workflows SA: Impersonate Video SA for Cloud Run execution
resource "google_service_account_iam_member" "workflows_sa_user" {
  service_account_id = google_service_account.video_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.workflows_sa.email}"
}

# Scheduler SA: Invoke Workflows
resource "google_project_iam_member" "scheduler_workflows_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

# ---------------------------------------------------------------------------
# 4. Pub/Sub Topic for Human Review Gate
# ---------------------------------------------------------------------------

resource "google_pubsub_topic" "video_reviews" {
  name = "weaware-video-reviews"
}

resource "google_pubsub_topic_iam_member" "video_pubsub_publisher" {
  topic  = google_pubsub_topic.video_reviews.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.video_sa.email}"
}

# ---------------------------------------------------------------------------
# 5. Cloud Run Service: weaware-video-api (Option A)
# ---------------------------------------------------------------------------

# Public Invocation: weaware-video-api allows allUsers at the Cloud Run IAM layer
# because:
# 1. /videos/review must be clickable from emails/notifications by human reviewers without Google auth.
# 2. Make.com polls /videos/next-approved without GCP IAM credentials.
# All security is strictly enforced at application layer:
# - Machine endpoints (/stories/*, /videos/next-approved, /videos/{id}/mark-published) require x-api-key.
# - Human review (/videos/review) requires valid, single-use, unexpired HMAC-SHA256 tokens and has sliding window rate limiting.
resource "google_cloud_run_v2_service_iam_member" "video_api_public_access" {
  location = google_cloud_run_v2_service.video_api.location
  name     = google_cloud_run_v2_service.video_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# 5. Cloud Run Service: weaware-video-api (Option A)
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "video_api" {
  name     = "weaware-video-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.video_sa.email

    containers {
      image = var.video_api_image

      resources {
        limits = {
          cpu    = "1000m"
          memory = "1024Mi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = "${var.project_id}:${var.region}:weaware-pg"
      }
      env {
        name  = "VIDEO_BUCKET_NAME"
        value = google_storage_bucket.video_assets.name
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }
}

# ---------------------------------------------------------------------------
# 6. Cloud Run Job: weaware-video-job (Batch pipeline runner)
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_job" "video_job" {
  name     = "weaware-video-job"
  location = var.region

  template {
    template {
      service_account = google_service_account.video_sa.email
      timeout         = "1800s" # 30 min max

      containers {
        image   = var.video_job_image
        command = ["python", "video/pipeline/runner.py"]

        resources {
          limits = {
            cpu    = "2000m"
            memory = "2048Mi"
          }
        }

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "GOOGLE_CLOUD_LOCATION"
          value = var.region
        }
        env {
          name  = "VIDEO_API_URL"
          value = google_cloud_run_v2_service.video_api.uri
        }
        env {
          name  = "VIDEO_BUCKET_NAME"
          value = google_storage_bucket.video_assets.name
        }
        env {
          name  = "VEO_MODEL_TIER"
          value = "fast"
        }
      }
    }
  }
}

# ---------------------------------------------------------------------------
# 7. Cloud Workflows: weaware-video-pipeline
# ---------------------------------------------------------------------------

resource "google_workflows_workflow" "video_pipeline" {
  name            = "weaware-video-pipeline"
  region          = var.region
  description     = "Orchestrates guard checks, video generation job, and review notifications"
  service_account = google_service_account.workflows_sa.email
  source_contents = file("${path.module}/workflow.yaml")
}

# ---------------------------------------------------------------------------
# 8. Cloud Scheduler: weaware-video-scheduler (Created PAUSED)
# ---------------------------------------------------------------------------

resource "google_cloud_scheduler_job" "video_scheduler" {
  name        = "weaware-video-scheduler"
  description = "Triggers WeAware Late Night video pipeline at 02:00 UTC on ingestion days"
  schedule    = "0 2 */2 * *"
  time_zone   = "Etc/UTC"
  paused      = true # Explicitly created paused per safety mandate

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/workflows/${google_workflows_workflow.video_pipeline.name}/executions"

    oauth_token {
      service_account_email = google_service_account.scheduler_sa.email
    }

    body = base64encode(jsonencode({
      argument = jsonencode({
        tier = "fast"
      })
    }))
  }
}
