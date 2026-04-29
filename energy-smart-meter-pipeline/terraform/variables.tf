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
  description = "S3 bucket name for silver/gold and run-log data"
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

variable "enable_step_functions" {
  description = "If true, Scheduler triggers Step Functions instead of Lambda"
  type        = bool
  default     = true
}

variable "pipeline_runner_lambda_arn" {
  description = "Lambda ARN for pipeline execution when Step Functions is disabled"
  type        = string
  default     = ""
}

variable "load_source_lambda_arn" {
  description = "Lambda ARN for source-loading step in Step Functions"
  type        = string
  default     = ""
}

variable "transform_lambda_arn" {
  description = "Lambda ARN for transform step in Step Functions"
  type        = string
  default     = ""
}

variable "qa_lambda_arn" {
  description = "Lambda ARN for QA step in Step Functions"
  type        = string
  default     = ""
}

variable "run_log_lambda_arn" {
  description = "Lambda ARN for run-log writing step in Step Functions"
  type        = string
  default     = ""
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
