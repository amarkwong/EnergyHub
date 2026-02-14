locals {
  api_name              = "${var.project_name}-${var.environment}-api"
  lambda_invoke_arn     = coalesce(var.lambda_invoke_arn, "")
  lambda_function_name  = coalesce(var.lambda_function_name, "")
  enable_lambda_routing = local.lambda_invoke_arn != "" && local.lambda_function_name != ""
}

resource "aws_apigatewayv2_api" "http" {
  count         = var.enabled ? 1 : 0
  name          = local.api_name
  protocol_type = "HTTP"

  cors_configuration {
    allow_headers = ["content-type", "authorization"]
    allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_origins = var.cors_allow_origins
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_stage" "default" {
  count       = var.enabled ? 1 : 0
  api_id      = aws_apigatewayv2_api.http[0].id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda_proxy" {
  count = var.enabled && local.enable_lambda_routing ? 1 : 0

  api_id                 = aws_apigatewayv2_api.http[0].id
  integration_type       = "AWS_PROXY"
  integration_uri        = local.lambda_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy" {
  count = var.enabled && local.enable_lambda_routing ? 1 : 0

  api_id    = aws_apigatewayv2_api.http[0].id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_proxy[0].id}"
}

resource "aws_apigatewayv2_route" "root" {
  count = var.enabled && local.enable_lambda_routing ? 1 : 0

  api_id    = aws_apigatewayv2_api.http[0].id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_proxy[0].id}"
}

resource "aws_lambda_permission" "allow_apigw" {
  count = var.enabled && local.enable_lambda_routing ? 1 : 0

  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = local.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http[0].execution_arn}/*/*"
}
