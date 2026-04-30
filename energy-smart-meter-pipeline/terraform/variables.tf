# Summary: Terraform input variables for AWS infrastructure and scheduling behavior.
variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-2"
}

variable "project_name" {
  description = "Project prefix used for resource naming"
  type        = string
  default     = "energy-smart-meter-pipeline"
}

variable "environment" {
  description = "Environment name (dev/test/prod)"
  type        = string
  default     = "dev"
}

variable "external_source_s3_uri" {
  description = "Read-only external Bronze dataset URI (S3 parquet/GeoParquet)"
  type        = string
  default     = "s3://weave.energy/smart-meter.parquet"
}

variable "data_bucket_name" {
  description = "S3 bucket name for silver/gold, run-log data, and Glue scripts"
  type        = string
}

variable "athena_results_bucket_name" {
  description = "S3 bucket for Athena query results"
  type        = string
}

variable "data_prefix" {
  description = "Prefix inside the data bucket"
  type        = string
  default     = "portfolio"
}

variable "glue_database_name" {
  description = "Glue database name"
  type        = string
  default     = "energy_smart_meter"
}

variable "preserve_data" {
  description = "When true, prevent accidental data bucket destruction"
  type        = bool
  default     = true
}

variable "daily_schedule_expression" {
  description = "EventBridge Scheduler cron or rate expression for daily runs"
  type        = string
  default     = "cron(0 2 * * ? *)"
}

variable "scheduler_timezone" {
  description = "Timezone for EventBridge Scheduler"
  type        = string
  default     = "Europe/London"
}

variable "glue_worker_type" {
  description = "Glue worker type for transform job"
  type        = string
  default     = "G.1X"
}

variable "glue_number_of_workers" {
  description = "Number of workers for Glue transform job"
  type        = number
  default     = 2
}

variable "enable_step_functions_wrapper" {
  description = "If true, create an optional Step Functions wrapper around the Glue job"
  type        = bool
  default     = false
}

variable "enable_backfill_one_off" {
  description = "When true, create a one-off backfill schedule"
  type        = bool
  default     = false
}

variable "backfill_schedule_expression" {
  description = "One-off at(...) schedule expression for manual backfill"
  type        = string
  default     = "at(2026-01-15T01:00:00)"
}

variable "backfill_run_date" {
  description = "Run date passed to one-off backfill invocation"
  type        = string
  default     = "2026-01-14"
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}
