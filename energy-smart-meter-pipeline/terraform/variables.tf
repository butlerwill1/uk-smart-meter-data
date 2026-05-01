# Summary: Terraform input variables for AWS infrastructure and scheduling behavior.
# This file defines operator-tunable settings used across all Terraform modules.

# Region where all AWS resources are created.
variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-2"
}

# Project name used as part of resource naming.
variable "project_name" {
  description = "Project prefix used for resource naming"
  type        = string
  default     = "energy-smart-meter-pipeline"
}

# Environment name to separate dev/test/prod deployments.
variable "environment" {
  description = "Environment name (dev/test/prod)"
  type        = string
  default     = "dev"
}

# Read-only external Bronze dataset location.
variable "external_source_s3_uri" {
  description = "Read-only external Bronze dataset URI (S3 parquet/GeoParquet)"
  type        = string
  default     = "s3://weave.energy/smart-meter.parquet"
}

# Primary data bucket for silver/gold outputs, run logs, and Glue scripts.
variable "data_bucket_name" {
  description = "S3 bucket name for silver/gold, run-log data, and Glue scripts"
  type        = string
}

# Bucket for Athena query output artifacts.
variable "athena_results_bucket_name" {
  description = "S3 bucket for Athena query results"
  type        = string
}

# Prefix under data bucket to isolate project files.
variable "data_prefix" {
  description = "Prefix inside the data bucket"
  type        = string
  default     = "portfolio"
}

# Glue database where external tables are registered.
variable "glue_database_name" {
  description = "Glue database name"
  type        = string
  default     = "energy_smart_meter"
}

# Toggle data-bucket protection from accidental destroy.
variable "preserve_data" {
  description = "When true, prevent accidental data bucket destruction"
  type        = bool
  default     = true
}

# Daily scheduler expression (cron(...) or rate(...)).
variable "daily_schedule_expression" {
  description = "EventBridge Scheduler cron or rate expression for daily runs"
  type        = string
  default     = "cron(0 2 * * ? *)"
}

# Timezone for EventBridge schedule evaluation.
variable "scheduler_timezone" {
  description = "Timezone for EventBridge Scheduler"
  type        = string
  default     = "Europe/London"
}

# Glue worker class used for transform job compute.
variable "glue_worker_type" {
  description = "Glue worker type for transform job"
  type        = string
  default     = "G.1X"
}

# Number of Glue workers for transform job.
variable "glue_number_of_workers" {
  description = "Number of workers for Glue transform job"
  type        = number
  default     = 2
}

# Optional visibility wrapper using Step Functions.
variable "enable_step_functions_wrapper" {
  description = "If true, create an optional Step Functions wrapper around the Glue job"
  type        = bool
  default     = false
}

# Toggle one-off backfill schedule creation.
variable "enable_backfill_one_off" {
  description = "When true, create a one-off backfill schedule"
  type        = bool
  default     = false
}

# One-off schedule expression (typically at(...)).
variable "backfill_schedule_expression" {
  description = "One-off at(...) schedule expression for manual backfill"
  type        = string
  default     = "at(2026-01-15T01:00:00)"
}

# Date passed into one-off backfill run.
variable "backfill_run_date" {
  description = "Run date passed to one-off backfill invocation"
  type        = string
  default     = "2026-01-14"
}

# Additional user-defined tags merged into common tags.
variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}

# Lake Formation principals (IAM user/role ARNs) that should be able to query tables.
# Example: ["arn:aws:iam::123456789012:role/Admin"]
variable "lakeformation_principal_arns" {
  description = "List of IAM principal ARNs to grant Lake Formation permissions"
  type        = list(string)
  default     = []
}

# Whether to grant DATA_LOCATION_ACCESS on S3 locations used by this pipeline.
variable "enable_lakeformation_data_location_permissions" {
  description = "Grant Lake Formation data location permissions for configured principals"
  type        = bool
  default     = true
}

# Whether Terraform should register S3 locations in Lake Formation.
# Keep false if your org already manages registrations centrally.
variable "enable_lakeformation_register_resources" {
  description = "Register pipeline S3 locations as Lake Formation resources"
  type        = bool
  default     = false
}

# Automatically include the current Terraform caller principal in Lake Formation grants.
variable "enable_lakeformation_auto_grant_current_principal" {
  description = "Auto-grant Lake Formation permissions to the current AWS caller principal"
  type        = bool
  default     = true
}
