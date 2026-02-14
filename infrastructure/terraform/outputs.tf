# Outputs for EnergyHub Infrastructure

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "backend_ecr_url" {
  description = "ECR repository URL for backend"
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_ecr_url" {
  description = "ECR repository URL for frontend"
  value       = aws_ecr_repository.frontend.repository_url
}

output "database_endpoint" {
  description = "RDS database endpoint"
  value       = module.database.endpoint
  sensitive   = true
}

output "load_balancer_dns" {
  description = "DNS name of the load balancer"
  value       = module.ecs.load_balancer_dns
}

output "serverless_phase_a_enabled" {
  description = "Whether Phase A serverless module scaffolding is enabled."
  value       = var.enable_serverless_phase_a
}

output "serverless_phase_b_enabled" {
  description = "Whether Phase B serverless resources are enabled."
  value       = var.enable_serverless_phase_b
}

output "planned_static_website_bucket" {
  description = "Planned frontend static website bucket name."
  value       = module.static_web.planned_website_bucket_name
}

output "planned_api_gateway_name" {
  description = "Planned API Gateway name."
  value       = module.api_gateway.planned_api_name
}

output "planned_worker_queues" {
  description = "Planned queue names for async workloads."
  value       = module.queues.planned_queue_names
}

output "planned_uploads_bucket" {
  description = "Planned uploads bucket for invoices and meter files."
  value       = module.storage.planned_uploads_bucket_name
}

output "serverless_api_endpoint" {
  description = "HTTP API endpoint for Lambda-backed backend."
  value       = module.api_gateway.api_endpoint
}

output "static_web_cloudfront_domain" {
  description = "CloudFront domain serving static frontend."
  value       = module.static_web.cloudfront_domain_name
}
