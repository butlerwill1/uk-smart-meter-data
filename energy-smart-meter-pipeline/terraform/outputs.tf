# Summary: Terraform outputs for core storage, metadata, and orchestration resource identifiers.
output "data_bucket_name" {
  value       = aws_s3_bucket.data.bucket
  description = "Data bucket that stores raw/silver/gold data and run logs"
}

output "athena_results_bucket_name" {
  value       = aws_s3_bucket.athena_results.bucket
  description = "Athena query results bucket"
}

output "glue_database_name" {
  value       = aws_glue_catalog_database.energy.name
  description = "Glue Data Catalog database name"
}

output "athena_workgroup_name" {
  value       = aws_athena_workgroup.smart_meter.name
  description = "Athena workgroup name"
}

output "state_machine_arn" {
  value       = var.enable_step_functions ? aws_sfn_state_machine.pipeline[0].arn : null
  description = "Step Functions state machine ARN when enabled"
}

output "daily_schedule_name" {
  value       = aws_scheduler_schedule.daily_pipeline.name
  description = "EventBridge Scheduler daily schedule name"
}
