output "article_audio_bucket" { value = google_storage_bucket.article_audio.name }
output "podcast_audio_bucket" { value = google_storage_bucket.podcast_audio.name }
output "audio_tasks_queue" { value = google_cloud_tasks_queue.audio_generation.name }
output "audio_tasks_service_account" { value = google_service_account.audio_tasks.email }
output "podcast_audio_public_origin" { value = "https://storage.googleapis.com/${google_storage_bucket.podcast_audio.name}" }
output "audio_task_worker_url" { value = trimsuffix(var.api_service_url, "/") }
output "podcast_editorial_secret_name" { value = google_secret_manager_secret.podcast_editorial_api_key.secret_id }
