# Summary: S3 storage resources for persistent pipeline datasets, Glue scripts, and Athena query results.
# Design goals:
# - keep data durable by default,
# - allow explicit ephemeral mode for teardown-heavy environments,
# - enforce encryption at rest.

# Persistent data bucket mode: prevents accidental destroy.
resource "aws_s3_bucket" "data_preserved" {
  count         = var.preserve_data ? 1 : 0
  bucket        = var.data_bucket_name
  force_destroy = false

  lifecycle {
    # Hard safety guard when preserve_data=true.
    prevent_destroy = true
  }

  tags = local.common_tags
}

# Ephemeral data bucket mode: allows full destroy when preserve_data=false.
resource "aws_s3_bucket" "data_ephemeral" {
  count         = var.preserve_data ? 0 : 1
  bucket        = var.data_bucket_name
  force_destroy = true
  tags          = local.common_tags
}

# Enable object versioning on whichever data bucket variant is active.
resource "aws_s3_bucket_versioning" "data" {
  bucket = local.data_bucket_id
  versioning_configuration {
    status = "Enabled"
  }
}

# Enforce SSE-S3 encryption on data bucket.
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = local.data_bucket_id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Dedicated bucket for Athena query result files.
resource "aws_s3_bucket" "athena_results" {
  bucket        = var.athena_results_bucket_name
  force_destroy = true
  tags          = local.common_tags
}

# Enforce SSE-S3 encryption on Athena results bucket.
resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
