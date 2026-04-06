# SQS stage queues (recommended when scaling)
# Each stage can scale independently, preventing heavy extraction from blocking ingestion.

resource "aws_sqs_queue" "q_ingest" {
  name                      = "${local.name}-q-ingest"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600 # 14 days
  tags = local.tags
}

resource "aws_sqs_queue" "q_extract" {
  name                      = "${local.name}-q-extract"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 1209600
  tags = local.tags
}

resource "aws_sqs_queue" "q_pricing" {
  name                      = "${local.name}-q-pricing"
  visibility_timeout_seconds = 600
  message_retention_seconds  = 1209600
  tags = local.tags
}

resource "aws_sqs_queue" "q_pack" {
  name                      = "${local.name}-q-pack"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 1209600
  tags = local.tags
}

resource "aws_sqs_queue" "q_send" {
  name                      = "${local.name}-q-send"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600
  tags = local.tags
}

# Optional DLQs (recommended) — sample for extract
resource "aws_sqs_queue" "dlq_extract" {
  name = "${local.name}-dlq-extract"
  message_retention_seconds = 1209600
  tags = local.tags
}

resource "aws_sqs_queue_redrive_policy" "extract_redrive" {
  queue_url = aws_sqs_queue.q_extract.id
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq_extract.arn
    maxReceiveCount     = 5
  })
}
