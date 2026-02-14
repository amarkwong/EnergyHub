output "api_id" {
  value = try(aws_apigatewayv2_api.http[0].id, null)
}

output "api_name" {
  value = try(aws_apigatewayv2_api.http[0].name, null)
}

output "api_endpoint" {
  value = try(aws_apigatewayv2_api.http[0].api_endpoint, null)
}

output "execution_arn" {
  value = try(aws_apigatewayv2_api.http[0].execution_arn, null)
}

output "planned_api_name" {
  value = var.enabled ? "${var.project_name}-${var.environment}-api" : null
}

output "phase_note" {
  value = var.enabled ? "Phase B resources enabled in api_gateway module." : "api_gateway module disabled."
}
