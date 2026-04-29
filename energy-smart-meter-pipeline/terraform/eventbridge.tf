# Summary: EventBridge Scheduler resources for daily and optional one-off backfill pipeline execution.
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
    arn      = var.enable_step_functions ? aws_sfn_state_machine.pipeline[0].arn : var.pipeline_runner_lambda_arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      trigger = "daily-schedule"
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
    arn      = var.enable_step_functions ? aws_sfn_state_machine.pipeline[0].arn : var.pipeline_runner_lambda_arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      run_date = var.backfill_run_date
      trigger  = "manual-backfill"
    })
  }
}
