# GCS Remote Backend Configuration for WeAware Video Pipeline
#
# DO NOT apply or run 'tofu init -migrate-state' until the bucket is created in Step (b).
#
# Bucket specifications:
#   - Name: weaware-tfstate-project-9ba21d45
#   - Location: us-central1
#   - Object Versioning: Enabled
#   - Uniform Bucket-Level Access: Enabled
#   - Public Access Prevention: Enforced
#   - Access restricted to project owner / deployment identities

terraform {
  backend "gcs" {
    bucket = "weaware-tfstate-project-9ba21d45"
    prefix = "video-pipeline"
  }
}
