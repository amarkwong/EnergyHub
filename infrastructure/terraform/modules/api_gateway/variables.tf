variable "enabled" {
  type    = bool
  default = false
}

variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "lambda_invoke_arn" {
  type    = string
  default = ""
}

variable "lambda_function_name" {
  type    = string
  default = ""
}

variable "cors_allow_origins" {
  type    = list(string)
  default = ["*"]
}
