variable "project_id" {
  type        = string
  description = "GCP Project ID"
  default     = "project-9ba21d45-1dfd-4108-b69"
}

variable "region" {
  type        = string
  description = "GCP Region"
  default     = "us-central1"
}

variable "video_api_image" {
  type        = string
  description = "Container image for weaware-video-api"
  default     = "us-central1-docker.pkg.dev/project-9ba21d45-1dfd-4108-b69/weaware-repo/weaware-video-api:latest"
}

variable "video_job_image" {
  type        = string
  description = "Container image for weaware-video-job"
  default     = "us-central1-docker.pkg.dev/project-9ba21d45-1dfd-4108-b69/weaware-repo/weaware-video-job:latest"
}

variable "ingestion_trigger_id" {
  type        = string
  description = "Cloud Build Trigger ID for ingestion pipeline guard check"
  default     = "c1ae5465-26cf-4c82-8370-5fd7e97ffa62"
}
