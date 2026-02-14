locals {
  function_name   = "${var.project_name}-${var.environment}-api"
  create_function = var.enabled && var.create_function && var.lambda_artifact_bucket != "" && var.lambda_artifact_key != ""
  use_vpc         = var.vpc_id != "" && length(var.private_subnet_ids) > 0
  s3_object_arns  = [for arn in var.allowed_bucket_arns : "${arn}/*"]
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda" {
  count              = var.enabled ? 1 : 0
  name               = "${local.function_name}-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

resource "aws_iam_role_policy" "lambda" {
  count = var.enabled ? 1 : 0
  name  = "${local.function_name}-policy"
  role  = aws_iam_role.lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Effect = "Allow"
          Action = [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
          ]
          Resource = "*"
        }
      ],
      local.use_vpc ? [
        {
          Effect = "Allow"
          Action = [
            "ec2:CreateNetworkInterface",
            "ec2:DescribeNetworkInterfaces",
            "ec2:DeleteNetworkInterface",
            "ec2:AssignPrivateIpAddresses",
            "ec2:UnassignPrivateIpAddresses"
          ]
          Resource = "*"
        }
      ] : [],
      length(var.allowed_secret_arns) > 0 ? [
        {
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = var.allowed_secret_arns
        }
      ] : [],
      length(var.allowed_queue_arns) > 0 ? [
        {
          Effect = "Allow"
          Action = [
            "sqs:SendMessage",
            "sqs:GetQueueAttributes",
            "sqs:GetQueueUrl"
          ]
          Resource = var.allowed_queue_arns
        }
      ] : [],
      length(var.allowed_bucket_arns) > 0 ? [
        {
          Effect   = "Allow"
          Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
          Resource = concat(var.allowed_bucket_arns, local.s3_object_arns)
        }
      ] : []
    )
  })
}

resource "aws_security_group" "lambda" {
  count       = var.enabled && local.use_vpc ? 1 : 0
  name_prefix = "${local.function_name}-sg-"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  count             = var.enabled ? 1 : 0
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_in_days
}

resource "aws_lambda_function" "api" {
  count = local.create_function ? 1 : 0

  function_name = local.function_name
  role          = aws_iam_role.lambda[0].arn
  runtime       = var.runtime
  handler       = var.handler
  timeout       = var.timeout_seconds
  memory_size   = var.memory_size

  s3_bucket = var.lambda_artifact_bucket
  s3_key    = var.lambda_artifact_key

  environment {
    variables = var.environment_variables
  }

  dynamic "vpc_config" {
    for_each = local.use_vpc ? [1] : []
    content {
      subnet_ids         = var.private_subnet_ids
      security_group_ids = [aws_security_group.lambda[0].id]
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda,
    aws_cloudwatch_log_group.lambda
  ]
}
