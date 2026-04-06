############################################
# ATHENA + GLUE AUDIT ANALYTICS (SCAFFOLD)
############################################
# Assumes your export job writes JSONL files partitioned by date:
# s3://<audit_bucket>/exports/send_events/date=YYYY-MM-DD/*.jsonl

variable "enable_athena" { type = bool default = false }
variable "audit_bucket_name" { type = string default = "" }

resource "aws_athena_workgroup" "audit" {
  count = var.enable_athena ? 1 : 0
  name  = "${local.name}-audit"
  configuration {
    enforce_workgroup_configuration = true
    publish_cloudwatch_metrics_enabled = true
    result_configuration {
      output_location = "s3://${var.audit_bucket_name}/athena-results/"
    }
  }
  tags = local.tags
}

resource "aws_glue_catalog_database" "audit" {
  count = var.enable_athena ? 1 : 0
  name  = replace("${local.name}_audit", "-", "_")
}

resource "aws_glue_catalog_table" "send_events" {
  count         = var.enable_athena ? 1 : 0
  name          = "send_events"
  database_name = aws_glue_catalog_database.audit[0].name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "classification" = "json"
    "projection.enabled" = "true"
    "projection.date.type" = "date"
    "projection.date.range" = "2025-01-01,NOW"
    "projection.date.format" = "yyyy-MM-dd"
    "storage.location.template" = "s3://${var.audit_bucket_name}/exports/send_events/date=${date}/"
  }

  storage_descriptor {
    location      = "s3://${var.audit_bucket_name}/exports/send_events/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info { serialization_library = "org.openx.data.jsonserde.JsonSerDe" }

    columns { name="tenant_id" type="bigint" }
    columns { name="id" type="bigint" }
    columns { name="status" type="string" }
    columns { name="reason" type="string" }
    columns { name="buyer" type="string" }
    columns { name="recipient" type="string" }
    columns { name="created_at" type="timestamp" }
    columns { name="metadata" type="string" }
  }

  partition_keys { name="date" type="string" }
}
