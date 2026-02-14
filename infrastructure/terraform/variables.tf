# Variables for EnergyHub Infrastructure

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "energyhub"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-2" # Sydney - closest to Australian users
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "enable_serverless_phase_a" {
  description = "Enable Phase A serverless module skeleton wiring (no resources created yet)."
  type        = bool
  default     = true
}

variable "domain_name" {
  description = "Primary domain for static web frontend (optional in Phase A)."
  type        = string
  default     = ""
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID for the frontend domain (optional in Phase A)."
  type        = string
  default     = ""
}

variable "lambda_artifact_bucket" {
  description = "S3 bucket used for Lambda deployment artifacts (optional in Phase A)."
  type        = string
  default     = ""
}

variable "enable_serverless_phase_b" {
  description = "Enable creation of Phase B serverless resources."
  type        = bool
  default     = false
}

variable "create_lambda_functions" {
  description = "Create Lambda functions (requires uploaded artifacts in S3)."
  type        = bool
  default     = false
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for custom frontend domain (optional)."
  type        = string
  default     = ""
}

variable "lambda_api_artifact_key" {
  description = "S3 key for API Lambda zip artifact."
  type        = string
  default     = ""
}

variable "lambda_worker_artifact_keys" {
  description = "S3 keys for worker Lambda zip artifacts keyed by worker name."
  type        = map(string)
  default     = {}
}
