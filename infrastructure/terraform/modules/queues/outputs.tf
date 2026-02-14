output "queue_names" {
  value = { for k, q in aws_sqs_queue.main : k => q.name }
}

output "queue_arns" {
  value = { for k, q in aws_sqs_queue.main : k => q.arn }
}

output "queue_urls" {
  value = { for k, q in aws_sqs_queue.main : k => q.url }
}

output "dlq_arns" {
  value = { for k, q in aws_sqs_queue.dlq : k => q.arn }
}

output "planned_queue_names" {
  value = var.enabled ? [
    "${var.project_name}-${var.environment}-reconciliation",
    "${var.project_name}-${var.environment}-invoice-parse",
    "${var.project_name}-${var.environment}-meter-processing"
  ] : []
}

output "phase_note" {
  value = var.enabled ? "Phase B resources enabled in queues module." : "Queues module disabled."
}
