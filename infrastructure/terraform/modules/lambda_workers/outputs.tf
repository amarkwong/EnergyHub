output "function_names" {
  value = { for k, fn in aws_lambda_function.worker : k => fn.function_name }
}

output "function_arns" {
  value = { for k, fn in aws_lambda_function.worker : k => fn.arn }
}

output "role_arn" {
  value = try(aws_iam_role.workers[0].arn, null)
}

output "security_group_id" {
  value = try(aws_security_group.workers[0].id, null)
}

output "planned_function_prefix" {
  value = var.enabled ? "${var.project_name}-${var.environment}-worker" : null
}

output "planned_artifact_bucket" {
  value = var.enabled && var.lambda_artifact_bucket != "" ? var.lambda_artifact_bucket : null
}

output "phase_note" {
  value = var.enabled ? "Phase B resources enabled in lambda_workers module." : "lambda_workers module disabled."
}
