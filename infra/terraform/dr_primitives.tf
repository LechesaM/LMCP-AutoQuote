# Disaster Recovery primitives (scaffold)
# - S3 cross-region replication (requires destination bucket in DR region)
# - RDS snapshots copied to DR region (can be automated via EventBridge+Lambda)

variable "enable_dr"  { type = bool default = false }
variable "dr_region"  { type = string default = "eu-west-1" }

# NOTE: Full DR is best implemented with a second Terraform workspace targeting dr_region,
# plus S3 replication rules and scheduled snapshot copy jobs.

# S3 replication role (scaffold)
data "aws_iam_policy_document" "s3_replication_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type = "Service" identifiers = ["s3.amazonaws.com"] }
  }
}

resource "aws_iam_role" "s3_replication" {
  count              = var.enable_dr ? 1 : 0
  name               = "${local.name}-s3-repl"
  assume_role_policy = data.aws_iam_policy_document.s3_replication_assume.json
}

# You will create destination buckets in DR region in a separate provider alias.
# Then add aws_s3_bucket_replication_configuration rules per bucket.
# We provide this as a blueprint because DR buckets must exist in the other region.
