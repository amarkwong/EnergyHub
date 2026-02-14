locals {
  worker_prefix    = "${var.project_name}-${var.environment}-worker"
  create_functions = var.enabled && var.create_functions && var.lambda_artifact_bucket != ""
  use_vpc          = var.vpc_id != "" && length(var.private_subnet_ids) > 0

  worker_defaults = {
    reconciliation   = "reconciliation.zip"
    invoice_parse    = "invoice_parse.zip"
    meter_processing = "meter_processing.zip"
    tariff_refresh   = "tariff_refresh.zip"
  }

  worker_artifact_keys = {
    for name, default_name in local.worker_defaults :
    name => lookup(var.lambda_artifact_keys, name, "${var.lambda_artifact_prefix}/${default_name}")
  }

  s3_object_arns = [for arn in var.allowed_bucket_arns : "${arn}/*"]
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

resource "aws_iam_role" "workers" {
  count              = var.enabled ? 1 : 0
  name               = "${local.worker_prefix}-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

resource "aws_iam_role_policy" "workers" {
  count = var.enabled ? 1 : 0
  name  = "${local.worker_prefix}-policy"
  role  = aws_iam_role.workers[0].id

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
      length(var.queue_arns) > 0 ? [
        {
          Effect = "Allow"
          Action = [
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
            "sqs:GetQueueUrl",
            "sqs:ChangeMessageVisibility"
          ]
          Resource = values(var.queue_arns)
        }
      ] : [],
      length(var.allowed_secret_arns) > 0 ? [
        {
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = var.allowed_secret_arns
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

resource "aws_security_group" "workers" {
  count       = var.enabled && local.use_vpc ? 1 : 0
  name_prefix = "${local.worker_prefix}-sg-"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_cloudwatch_log_group" "workers" {
  for_each = local.create_functions ? local.worker_artifact_keys : {}

  name              = "/aws/lambda/${local.worker_prefix}-${replace(each.key, "_", "-")}"
  retention_in_days = var.log_retention_in_days
}

resource "aws_lambda_function" "worker" {
  for_each = local.create_functions ? local.worker_artifact_keys : {}

  function_name = "${local.worker_prefix}-${replace(each.key, "_", "-")}"
  role          = aws_iam_role.workers[0].arn
  runtime       = var.runtime
  handler       = var.handler
  timeout       = var.timeout_seconds
  memory_size   = var.memory_size

  s3_bucket = var.lambda_artifact_bucket
  s3_key    = each.value

  environment {
    variables = merge(var.environment_variables, {
      WORKER_NAME = each.key
      QUEUE_URL   = lookup(var.queue_urls, each.key, "")
    })
  }

  dynamic "vpc_config" {
    for_each = local.use_vpc ? [1] : []
    content {
      subnet_ids         = var.private_subnet_ids
      security_group_ids = [aws_security_group.workers[0].id]
    }
  }

  depends_on = [
    aws_iam_role_policy.workers,
    aws_cloudwatch_log_group.workers
  ]
}

resource "aws_lambda_event_source_mapping" "queue_trigger" {
  for_each = {
    for key, queue_arn in var.queue_arns : key => queue_arn
    if local.create_functions && contains(keys(aws_lambda_function.worker), key)
  }

  event_source_arn = each.value
  function_name    = aws_lambda_function.worker[each.key].arn
  batch_size       = var.sqs_batch_size
}

resource "aws_cloudwatch_event_rule" "tariff_refresh" {
  count = local.create_functions && var.enable_tariff_refresh_schedule ? 1 : 0

  name                = "${local.worker_prefix}-tariff-refresh"
  description         = "Monthly tariff and plan refresh trigger"
  schedule_expression = var.tariff_refresh_schedule_expression
}

resource "aws_cloudwatch_event_target" "tariff_refresh" {
  count = local.create_functions && var.enable_tariff_refresh_schedule ? 1 : 0

  rule      = aws_cloudwatch_event_rule.tariff_refresh[0].name
  target_id = "tariff-refresh-lambda"
  arn       = aws_lambda_function.worker["tariff_refresh"].arn
}

resource "aws_lambda_permission" "allow_eventbridge_tariff_refresh" {
  count = local.create_functions && var.enable_tariff_refresh_schedule ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridgeTariffRefresh"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker["tariff_refresh"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.tariff_refresh[0].arn
}
