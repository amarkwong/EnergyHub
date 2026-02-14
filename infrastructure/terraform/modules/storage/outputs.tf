output "uploads_bucket_name" {
  value = try(aws_s3_bucket.this["uploads"].bucket, null)
}

output "exports_bucket_name" {
  value = try(aws_s3_bucket.this["exports"].bucket, null)
}

output "lambda_artifacts_bucket_name" {
  value = try(aws_s3_bucket.this["lambda_artifacts"].bucket, null)
}

output "uploads_bucket_arn" {
  value = try(aws_s3_bucket.this["uploads"].arn, null)
}

output "exports_bucket_arn" {
  value = try(aws_s3_bucket.this["exports"].arn, null)
}

output "lambda_artifacts_bucket_arn" {
  value = try(aws_s3_bucket.this["lambda_artifacts"].arn, null)
}

output "planned_uploads_bucket_name" {
  value = var.enabled ? "${var.project_name}-${var.environment}-uploads" : null
}

output "planned_exports_bucket_name" {
  value = var.enabled ? "${var.project_name}-${var.environment}-exports" : null
}

output "phase_note" {
  value = var.enabled ? "Phase B resources enabled in storage module." : "Storage module disabled."
}
