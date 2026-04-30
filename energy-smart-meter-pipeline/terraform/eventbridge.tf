# Summary: EventBridge Scheduler resources to trigger the AWS Glue transform job daily and for one-off backfills.
resource "aws_scheduler_schedule" "daily_pipeline" {
  name                         = "${local.name_prefix}-daily"
  group_name                   = "default"
  schedule_expression          = var.daily_schedule_expression
  schedule_expression_timezone = var.scheduler_timezone
  state                        = "ENABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:glue:startJobRun"
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      JobName = aws_glue_job.transform_daily.name
      Arguments = {
        "--run-date" = "AUTO"
      }
    })
  }
}

resource "aws_scheduler_schedule" "one_off_backfill" {
  count               = var.enable_backfill_one_off ? 1 : 0
  name                = "${local.name_prefix}-backfill-${replace(var.backfill_run_date, "-", "")}"
  group_name          = "default"
  schedule_expression = var.backfill_schedule_expression
  state               = "ENABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:glue:startJobRun"
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      JobName = aws_glue_job.transform_daily.name
      Arguments = {
        "--run-date" = var.backfill_run_date
      }
    })
  }
}
