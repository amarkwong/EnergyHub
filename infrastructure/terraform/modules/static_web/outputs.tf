output "website_bucket_name" {
  value = try(aws_s3_bucket.website[0].bucket, null)
}

output "logs_bucket_name" {
  value = try(aws_s3_bucket.logs[0].bucket, null)
}

output "cloudfront_distribution_id" {
  value = try(aws_cloudfront_distribution.website[0].id, null)
}

output "cloudfront_domain_name" {
  value = try(aws_cloudfront_distribution.website[0].domain_name, null)
}

output "planned_website_bucket_name" {
  value = var.enabled ? "${var.project_name}-${var.environment}-web" : null
}

output "planned_logs_bucket_name" {
  value = var.enabled ? "${var.project_name}-${var.environment}-web-logs" : null
}

output "planned_domain_name" {
  value = var.enabled && var.domain_name != "" ? var.domain_name : null
}

output "phase_note" {
  value = var.enabled ? "Phase B resources enabled in static_web module." : "static_web module disabled."
}
