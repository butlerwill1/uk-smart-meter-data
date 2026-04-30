# Summary: S3 storage resources for persistent pipeline datasets, Glue scripts, and Athena query results.
resource "aws_s3_bucket" "data_preserved" {
  count         = var.preserve_data ? 1 : 0
  bucket        = var.data_bucket_name
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }

  tags = local.common_tags
}

resource "aws_s3_bucket" "data_ephemeral" {
  count         = var.preserve_data ? 0 : 1
  bucket        = var.data_bucket_name
  force_destroy = true
  tags          = local.common_tags
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = local.data_bucket_id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = local.data_bucket_id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket" "athena_results" {
  bucket        = var.athena_results_bucket_name
  force_destroy = true
  tags          = local.common_tags
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
