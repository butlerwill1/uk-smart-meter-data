# Summary: IAM roles and policies for EventBridge Scheduler and optional Step Functions orchestration.
resource "aws_iam_role" "scheduler" {
  name = "${local.name_prefix}-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role" "step_functions" {
  count = var.enable_step_functions ? 1 : 0
  name  = "${local.name_prefix}-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name = "${local.name_prefix}-scheduler-invoke-policy"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      var.enable_step_functions ? [
        {
          Effect   = "Allow"
          Action   = ["states:StartExecution"]
          Resource = [aws_sfn_state_machine.pipeline[0].arn]
        }
      ] : [],
      (!var.enable_step_functions && var.pipeline_runner_lambda_arn != "") ? [
        {
          Effect   = "Allow"
          Action   = ["lambda:InvokeFunction"]
          Resource = [var.pipeline_runner_lambda_arn]
        }
      ] : []
    )
  })
}

resource "aws_iam_role_policy" "step_functions_tasks" {
  count = var.enable_step_functions ? 1 : 0
  name  = "${local.name_prefix}-sfn-task-policy"
  role  = aws_iam_role.step_functions[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = compact([
          var.load_source_lambda_arn,
          var.transform_lambda_arn,
          var.qa_lambda_arn,
          var.run_log_lambda_arn,
        ])
      }
    ]
  })
}
