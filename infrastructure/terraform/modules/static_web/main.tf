locals {
  website_bucket_name = "${var.project_name}-${var.environment}-web"
  logs_bucket_name    = "${var.project_name}-${var.environment}-web-logs"
  use_custom_domain   = var.domain_name != "" && var.acm_certificate_arn != ""
}

resource "aws_s3_bucket" "website" {
  count  = var.enabled ? 1 : 0
  bucket = local.website_bucket_name
}

resource "aws_s3_bucket_public_access_block" "website" {
  count = var.enabled ? 1 : 0

  bucket                  = aws_s3_bucket.website[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "website" {
  count  = var.enabled ? 1 : 0
  bucket = aws_s3_bucket.website[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "website" {
  count  = var.enabled ? 1 : 0
  bucket = aws_s3_bucket.website[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket" "logs" {
  count  = var.enabled ? 1 : 0
  bucket = local.logs_bucket_name
}

resource "aws_s3_bucket_public_access_block" "logs" {
  count = var.enabled ? 1 : 0

  bucket                  = aws_s3_bucket.logs[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "website" {
  count                             = var.enabled ? 1 : 0
  name                              = "${var.project_name}-${var.environment}-web-oac"
  description                       = "OAC for static web bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "website" {
  count = var.enabled ? 1 : 0

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = local.use_custom_domain ? [var.domain_name] : []

  origin {
    domain_name              = aws_s3_bucket.website[0].bucket_regional_domain_name
    origin_id                = "s3-${aws_s3_bucket.website[0].id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.website[0].id
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "s3-${aws_s3_bucket.website[0].id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  dynamic "viewer_certificate" {
    for_each = local.use_custom_domain ? [1] : []
    content {
      acm_certificate_arn      = var.acm_certificate_arn
      ssl_support_method       = "sni-only"
      minimum_protocol_version = "TLSv1.2_2021"
    }
  }

  dynamic "viewer_certificate" {
    for_each = local.use_custom_domain ? [] : [1]
    content {
      cloudfront_default_certificate = true
    }
  }
}

data "aws_iam_policy_document" "website_bucket_policy" {
  count = var.enabled ? 1 : 0

  statement {
    sid    = "AllowCloudFrontServicePrincipalReadOnly"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions = ["s3:GetObject"]

    resources = [
      "${aws_s3_bucket.website[0].arn}/*"
    ]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.website[0].arn]
    }
  }
}

resource "aws_s3_bucket_policy" "website" {
  count  = var.enabled ? 1 : 0
  bucket = aws_s3_bucket.website[0].id
  policy = data.aws_iam_policy_document.website_bucket_policy[0].json
}

resource "aws_route53_record" "website_alias" {
  count = var.enabled && local.use_custom_domain && var.hosted_zone_id != "" ? 1 : 0

  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.website[0].domain_name
    zone_id                = aws_cloudfront_distribution.website[0].hosted_zone_id
    evaluate_target_health = false
  }
}
