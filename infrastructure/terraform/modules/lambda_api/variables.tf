variable "enabled" {
  type    = bool
  default = false
}

variable "create_function" {
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

variable "lambda_artifact_key" {
  type    = string
  default = ""
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
  default = 30
}

variable "memory_size" {
  type    = number
  default = 512
}

variable "log_retention_in_days" {
  type    = number
  default = 30
}

variable "vpc_id" {
  type    = string
  default = ""
}

variable "private_subnet_ids" {
  type    = list(string)
  default = []
}

variable "allowed_secret_arns" {
  type    = list(string)
  default = []
}

variable "allowed_bucket_arns" {
  type    = list(string)
  default = []
}

variable "allowed_queue_arns" {
  type    = list(string)
  default = []
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}
