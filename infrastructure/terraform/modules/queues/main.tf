locals {
  queue_names = {
    reconciliation   = "${var.project_name}-${var.environment}-reconciliation"
    invoice_parse    = "${var.project_name}-${var.environment}-invoice-parse"
    meter_processing = "${var.project_name}-${var.environment}-meter-processing"
  }
}

resource "aws_sqs_queue" "dlq" {
  for_each = var.enabled ? local.queue_names : {}

  name                      = "${each.value}-dlq"
  message_retention_seconds = 1209600 # 14 days
}

resource "aws_sqs_queue" "main" {
  for_each = var.enabled ? local.queue_names : {}

  name                       = each.value
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = var.max_receive_count
  })
}
