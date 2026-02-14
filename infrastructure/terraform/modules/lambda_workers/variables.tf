variable "enabled" {
  type    = bool
  default = false
}

variable "create_functions" {
  type    = bool
  default = false
}

variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "lambda_artifact_bucket" {
  type    = string
  default = ""
}

variable "lambda_artifact_prefix" {
  type    = string
  default = "lambdas/workers"
}

variable "lambda_artifact_keys" {
  type    = map(string)
  default = {}
}

variable "runtime" {
  type    = string
  default = "python3.12"
}

variable "handler" {
  type    = string
  default = "app.lambda_handler"
}

variable "timeout_seconds" {
  type    = number
  default = 120
}

variable "memory_size" {
  type    = number
  default = 1024
}

variable "log_retention_in_days" {
  type    = number
  default = 30
}

variable "sqs_batch_size" {
  type    = number
  default = 10
}

variable "vpc_id" {
  type    = string
  default = ""
}

variable "private_subnet_ids" {
  type    = list(string)
  default = []
}

variable "queue_arns" {
  type    = map(string)
  default = {}
}

variable "queue_urls" {
  type    = map(string)
  default = {}
}

variable "allowed_secret_arns" {
  type    = list(string)
  default = []
}

variable "allowed_bucket_arns" {
  type    = list(string)
  default = []
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}

variable "enable_tariff_refresh_schedule" {
  type    = bool
  default = true
}

variable "tariff_refresh_schedule_expression" {
  type    = string
  default = "cron(0 0 1 * ? *)"
}
