# Summary: Terraform outputs for core storage, metadata, orchestration, and Glue execution resources.
output "data_bucket_name" {
  value       = local.data_bucket_bucket
  description = "Data bucket that stores silver/gold data, run logs, and Glue scripts"
}

output "athena_results_bucket_name" {
  value       = aws_s3_bucket.athena_results.bucket
  description = "Athena query results bucket"
}

output "glue_database_name" {
  value       = aws_glue_catalog_database.energy.name
  description = "Glue Data Catalog database name"
}

output "transform_glue_job_name" {
  value       = aws_glue_job.transform_daily.name
  description = "AWS Glue job name for daily PySpark transform"
}

output "transform_script_s3_uri" {
  value       = "s3://${aws_s3_object.transform_script.bucket}/${aws_s3_object.transform_script.key}"
  description = "S3 URI of uploaded transform_daily.py script"
}

output "athena_workgroup_name" {
  value       = aws_athena_workgroup.smart_meter.name
  description = "Athena workgroup name"
}

output "state_machine_arn" {
  value       = var.enable_step_functions_wrapper ? aws_sfn_state_machine.pipeline[0].arn : null
  description = "Optional Step Functions state machine ARN"
}

output "daily_schedule_name" {
  value       = aws_scheduler_schedule.daily_pipeline.name
  description = "EventBridge Scheduler daily schedule name"
}
