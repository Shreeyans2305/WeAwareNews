output "video_bucket" {
  description = "GCS bucket for video assets and runs"
  value       = google_storage_bucket.video_assets.name
}

output "video_api_url" {
  description = "Cloud Run URL for weaware-video-api"
  value       = google_cloud_run_v2_service.video_api.uri
}

output "video_service_account" {
  description = "Runtime service account for video operations"
  value       = google_service_account.video_sa.email
}

output "workflows_service_account" {
  description = "Service account for Cloud Workflows orchestration"
  value       = google_service_account.workflows_sa.email
}

output "scheduler_job_name" {
  description = "Name of the created Cloud Scheduler job"
  value       = google_cloud_scheduler_job.video_scheduler.name
}
