############################################
# CodeDeploy Revisions Bucket (for revision.zip)
############################################

variable "enable_codedeploy_bucket" { type = bool default = true }

resource "aws_s3_bucket" "codedeploy_revisions" {
  count  = var.enable_codedeploy_bucket ? 1 : 0
  bucket = "${local.name}-codedeploy-revisions"
  tags   = local.tags
}

resource "aws_s3_bucket_public_access_block" "codedeploy_revisions_pab" {
  count                   = var.enable_codedeploy_bucket ? 1 : 0
  bucket                  = aws_s3_bucket.codedeploy_revisions[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "codedeploy_revisions_v" {
  count  = var.enable_codedeploy_bucket ? 1 : 0
  bucket = aws_s3_bucket.codedeploy_revisions[0].id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "codedeploy_revisions_enc" {
  count  = var.enable_codedeploy_bucket ? 1 : 0
  bucket = aws_s3_bucket.codedeploy_revisions[0].id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

output "codedeploy_bucket_name" {
  value       = var.enable_codedeploy_bucket ? aws_s3_bucket.codedeploy_revisions[0].bucket : null
  description = "Set GitHub secret CODEDEPLOY_BUCKET to this"
}
