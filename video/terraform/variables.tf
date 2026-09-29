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

variable "image_tag" {
  type        = string
  description = "Image tag from Cloud Build (e.g. $BUILD_ID or specific commit)"
  default     = "build-initial"
  validation {
    condition     = var.image_tag != "latest" && length(var.image_tag) > 0
    error_message = "Deploying with ':latest' image tag is strictly prohibited. Provide a valid BUILD_ID or release tag."
  }
}

variable "video_api_image" {
  type        = string
  description = "Explicit container image for weaware-video-api (defaults to repo with var.image_tag)"
  default     = ""
  validation {
    condition     = !can(regex(".*:latest$", var.video_api_image))
    error_message = "Deploying with ':latest' image tag is strictly prohibited."
  }
}

variable "video_job_image" {
  type        = string
  description = "Explicit container image for weaware-video-job (defaults to repo with var.image_tag)"
  default     = ""
  validation {
    condition     = !can(regex(".*:latest$", var.video_job_image))
    error_message = "Deploying with ':latest' image tag is strictly prohibited."
  }
}

variable "ingestion_trigger_id" {
  type        = string
  description = "Cloud Build Trigger ID for ingestion pipeline guard check"
  default     = "c1ae5465-26cf-4c82-8370-5fd7e97ffa62"
}
