terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.45"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "current" {}

resource "google_project_service" "audio_apis" {
  for_each = toset([
    "cloudtasks.googleapis.com",
    "texttospeech.googleapis.com",
    "storage.googleapis.com",
    "iamcredentials.googleapis.com",
    "secretmanager.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "article_audio" {
  name                        = "${var.project_id}-article-audio"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  depends_on                  = [google_project_service.audio_apis]
}

resource "google_storage_bucket" "podcast_audio" {
  name                        = "${var.project_id}-podcast-audio"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  # Published podcast episodes must be fetchable by podcast applications.
  public_access_prevention = "inherited"
  force_destroy            = false
  depends_on               = [google_project_service.audio_apis]
}

resource "google_storage_bucket_iam_member" "podcast_public_read" {
  bucket = google_storage_bucket.podcast_audio.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

resource "google_service_account" "audio_tasks" {
  account_id   = "weaware-audio-tasks"
  display_name = "WeAware audio task identity"
}

resource "google_secret_manager_secret" "podcast_editorial_api_key" {
  secret_id = "podcast-editorial-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.audio_apis]
}

resource "google_secret_manager_secret_iam_member" "api_reads_podcast_editorial_key" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.podcast_editorial_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.api_service_account_email}"
}

resource "google_cloud_tasks_queue" "audio_generation" {
  name     = "weaware-audio-generation"
  location = var.region
  rate_limits {
    max_dispatches_per_second = 2
    max_concurrent_dispatches = 5
  }
  retry_config {
    max_attempts       = 5
    max_retry_duration = "3600s"
    min_backoff        = "10s"
    max_backoff        = "300s"
  }
  depends_on = [google_project_service.audio_apis]
}

resource "google_project_iam_member" "api_tasks_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${var.api_service_account_email}"
}

resource "google_storage_bucket_iam_member" "api_article_audio_creator" {
  bucket = google_storage_bucket.article_audio.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${var.api_service_account_email}"
}

resource "google_storage_bucket_iam_member" "api_article_audio_reader" {
  bucket = google_storage_bucket.article_audio.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.api_service_account_email}"
}

resource "google_storage_bucket_iam_member" "api_podcast_audio_creator" {
  bucket = google_storage_bucket.podcast_audio.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${var.api_service_account_email}"
}

resource "google_storage_bucket_iam_member" "api_podcast_audio_reader" {
  bucket = google_storage_bucket.podcast_audio.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.api_service_account_email}"
}

resource "google_service_account_iam_member" "api_may_mint_task_tokens" {
  service_account_id = google_service_account.audio_tasks.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.api_service_account_email}"
}

resource "google_service_account_iam_member" "api_signs_article_urls" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.api_service_account_email}"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${var.api_service_account_email}"
}

locals {
  cloud_tasks_agent = "service-${data.google_project.current.number}@gcp-sa-cloudtasks.iam.gserviceaccount.com"
}

resource "google_service_account_iam_member" "tasks_agent_may_mint_oidc" {
  service_account_id = google_service_account.audio_tasks.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.cloud_tasks_agent}"
}

resource "google_service_account_iam_member" "tasks_agent_token_creator" {
  service_account_id = google_service_account.audio_tasks.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${local.cloud_tasks_agent}"
}
