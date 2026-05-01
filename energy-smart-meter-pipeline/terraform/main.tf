# Summary: Core Terraform provider and shared local values for the smart meter pipeline stack.
# Purpose:
# - Configure Terraform and providers.
# - Define shared naming/tagging conventions.
# - Define canonical S3 locations used across resources.
# - Derive external source bucket name for IAM policy generation.

terraform {
  # Require a modern Terraform CLI version.
  required_version = ">= 1.5.0"

  # Providers used by this stack:
  # - aws: all AWS infrastructure resources.
  # - archive: package local Python source for Glue job dependencies.
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.5"
    }
  }
}

# AWS provider configuration uses region from variables.
provider "aws" {
  region = var.aws_region
}

locals {
  # Common resource naming prefix for environment isolation.
  name_prefix = "${var.project_name}-${var.environment}"

  # Standard tags attached to all tagged resources.
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags,
  )

  # Select the active data bucket resource based on preserve_data setting.
  data_bucket_id     = var.preserve_data ? aws_s3_bucket.data_preserved[0].id : aws_s3_bucket.data_ephemeral[0].id
  data_bucket_arn    = var.preserve_data ? aws_s3_bucket.data_preserved[0].arn : aws_s3_bucket.data_ephemeral[0].arn
  data_bucket_bucket = var.preserve_data ? aws_s3_bucket.data_preserved[0].bucket : aws_s3_bucket.data_ephemeral[0].bucket

  # Canonical dataset locations used by Glue Catalog external tables.
  external_raw_location = var.external_source_s3_uri
  silver_location       = "s3://${var.data_bucket_name}/${var.data_prefix}/energy/silver/smart_meter_half_hourly_clean/"
  gold_peak_location    = "s3://${var.data_bucket_name}/${var.data_prefix}/energy/gold/gold_peak_demand_substation_day/"
  gold_profile_location = "s3://${var.data_bucket_name}/${var.data_prefix}/energy/gold/gold_avg_load_profile_day/"
  run_log_location      = "s3://${var.data_bucket_name}/${var.data_prefix}/energy/meta/pipeline_run_log/"

  # Athena query results location.
  athena_output_location = "s3://${var.athena_results_bucket_name}/athena-results/"

  # Parse source URI to extract source bucket for IAM read grants.
  external_source_no_scheme = trimprefix(var.external_source_s3_uri, "s3://")
  external_source_parts     = split("/", local.external_source_no_scheme)
  external_source_bucket    = local.external_source_parts[0]


  # Current caller ARN from STS (may be assumed-role ARN).
  caller_principal_arn = data.aws_caller_identity.current.arn

  # Normalize STS assumed-role ARN to IAM role ARN for Lake Formation grants.
  caller_iam_principal_arn = can(regex(":assumed-role/", local.caller_principal_arn)) ? regexreplace(
    local.caller_principal_arn,
    "^arn:aws:sts::([0-9]+):assumed-role/(.+)/[^/]+$",
    "arn:aws:iam::$1:role/$2",
  ) : local.caller_principal_arn
}

# Current AWS account metadata for future extension and debugging.
data "aws_caller_identity" "current" {}
