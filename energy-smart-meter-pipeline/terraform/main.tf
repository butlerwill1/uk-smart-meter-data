# Summary: Core Terraform provider and shared local values for the smart meter pipeline stack.
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags,
  )

  external_raw_location = var.external_source_s3_uri
  silver_location       = "s3://${var.data_bucket_name}/${var.data_prefix}/energy/silver/smart_meter_half_hourly_clean/"
  gold_peak_location    = "s3://${var.data_bucket_name}/${var.data_prefix}/energy/gold/gold_peak_demand_substation_day/"
  gold_profile_location = "s3://${var.data_bucket_name}/${var.data_prefix}/energy/gold/gold_avg_load_profile_day/"
  run_log_location      = "s3://${var.data_bucket_name}/${var.data_prefix}/energy/meta/pipeline_run_log/"

  athena_output_location = "s3://${var.athena_results_bucket_name}/athena-results/"
}

data "aws_caller_identity" "current" {}
