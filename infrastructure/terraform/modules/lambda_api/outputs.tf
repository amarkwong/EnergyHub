output "function_name" {
  value = try(aws_lambda_function.api[0].function_name, null)
}

output "function_arn" {
  value = try(aws_lambda_function.api[0].arn, null)
}

output "invoke_arn" {
  value = try(aws_lambda_function.api[0].invoke_arn, null)
}

output "role_arn" {
  value = try(aws_iam_role.lambda[0].arn, null)
}

output "security_group_id" {
  value = try(aws_security_group.lambda[0].id, null)
}

output "planned_function_prefix" {
  value = var.enabled ? "${var.project_name}-${var.environment}-api" : null
}

output "planned_artifact_bucket" {
  value = var.enabled && var.lambda_artifact_bucket != "" ? var.lambda_artifact_bucket : null
}

output "phase_note" {
  value = var.enabled ? "Phase B resources enabled in lambda_api module." : "lambda_api module disabled."
}
