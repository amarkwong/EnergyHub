# EnergyHub Infrastructure - AWS

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.39.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "= 3.5.1"
    }
  }

  # Backend for state storage (configure as needed)
  # backend "s3" {
  #   bucket = "energyhub-terraform-state"
  #   key    = "terraform.tfstate"
  #   region = "ap-southeast-2"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "EnergyHub"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# VPC
module "vpc" {
  source = "./modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
}

# ECR Repositories
resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${var.project_name}-frontend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# RDS PostgreSQL
module "database" {
  source = "./modules/database"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  db_instance_class  = var.db_instance_class
}

# ECS Cluster
module "ecs" {
  source = "./modules/ecs"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  public_subnet_ids  = module.vpc.public_subnet_ids

  backend_image  = aws_ecr_repository.backend.repository_url
  frontend_image = aws_ecr_repository.frontend.repository_url
  database_url   = module.database.connection_string
}

# Phase A: serverless/static architecture skeleton (no runtime resources yet)
module "static_web" {
  source = "./modules/static_web"

  enabled             = var.enable_serverless_phase_b
  project_name        = var.project_name
  environment         = var.environment
  domain_name         = var.domain_name
  hosted_zone_id      = var.hosted_zone_id
  acm_certificate_arn = var.acm_certificate_arn
}

module "api_gateway" {
  source = "./modules/api_gateway"

  enabled              = var.enable_serverless_phase_b
  project_name         = var.project_name
  environment          = var.environment
  lambda_invoke_arn    = coalesce(module.lambda_api.invoke_arn, "")
  lambda_function_name = coalesce(module.lambda_api.function_name, "")
}

module "lambda_api" {
  source = "./modules/lambda_api"

  enabled                = var.enable_serverless_phase_b
  create_function        = var.create_lambda_functions
  project_name           = var.project_name
  environment            = var.environment
  lambda_artifact_bucket = var.lambda_artifact_bucket != "" ? var.lambda_artifact_bucket : module.storage.lambda_artifacts_bucket_name
  lambda_artifact_key    = var.lambda_api_artifact_key
  vpc_id                 = module.vpc.vpc_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  allowed_secret_arns    = [module.database.password_secret_arn]
  allowed_bucket_arns = compact([
    module.storage.uploads_bucket_arn,
    module.storage.exports_bucket_arn,
    module.storage.lambda_artifacts_bucket_arn,
  ])
  allowed_queue_arns = values(module.queues.queue_arns)
  environment_variables = {
    DATABASE_URL_SECRET_ARN = module.database.password_secret_arn
  }
}

module "lambda_workers" {
  source = "./modules/lambda_workers"

  enabled                = var.enable_serverless_phase_b
  create_functions       = var.create_lambda_functions
  project_name           = var.project_name
  environment            = var.environment
  lambda_artifact_bucket = var.lambda_artifact_bucket != "" ? var.lambda_artifact_bucket : module.storage.lambda_artifacts_bucket_name
  lambda_artifact_keys   = var.lambda_worker_artifact_keys
  vpc_id                 = module.vpc.vpc_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  queue_arns             = module.queues.queue_arns
  queue_urls             = module.queues.queue_urls
  allowed_secret_arns    = [module.database.password_secret_arn]
  allowed_bucket_arns = compact([
    module.storage.uploads_bucket_arn,
    module.storage.exports_bucket_arn,
    module.storage.lambda_artifacts_bucket_arn,
  ])
  environment_variables = {
    DATABASE_URL_SECRET_ARN = module.database.password_secret_arn
  }
}

module "queues" {
  source = "./modules/queues"

  enabled      = var.enable_serverless_phase_b
  project_name = var.project_name
  environment  = var.environment
}

module "storage" {
  source = "./modules/storage"

  enabled      = var.enable_serverless_phase_b
  project_name = var.project_name
  environment  = var.environment
}
