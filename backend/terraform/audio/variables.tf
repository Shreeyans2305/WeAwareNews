variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "api_service_account_email" {
  description = "Runtime service account used by the existing weaware-api Cloud Run service."
  type        = string
}
variable "api_service_url" {
  description = "Deployed HTTPS URL of the existing weaware-api service."
  type        = string
}
