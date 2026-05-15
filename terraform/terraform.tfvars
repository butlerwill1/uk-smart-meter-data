aws_region                 = "eu-west-2"
project_name               = "energy-smart-meter-pipeline"
environment                = "dev"
external_source_s3_uri     = "s3://weave.energy/smart-meter.parquet"
data_bucket_name           = "weave-smart-meter-data"
athena_results_bucket_name = "smart-meter-athena-results"
data_prefix                = "portfolio"
preserve_data              = true

glue_worker_type              = "G.1X"
glue_number_of_workers        = 2
enable_step_functions_wrapper = false
enable_daily_schedule         = false

daily_schedule_expression = "cron(0 2 * * ? *)"
scheduler_timezone        = "Europe/London"

enable_backfill_one_off      = false
backfill_schedule_expression = "at(2026-01-15T01:00:00)"
backfill_run_date            = "2026-01-14"
# IAM-only mode: disable Lake Formation resource management from this stack.
enable_lakeformation_auto_grant_current_principal = false
lakeformation_principal_arns                      = []
enable_lakeformation_data_location_permissions    = false
enable_lakeformation_register_resources           = false

tags = {
  Project  = "uk-smart-meter"
  CostScope = "portfolio"
  Owner = "will"
}
