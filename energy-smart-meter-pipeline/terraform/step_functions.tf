# Summary: Optional Step Functions wrapper that starts the same AWS Glue transform job and waits for completion.
# This is optional visualization/orchestration and is disabled unless explicitly enabled.

# Step Functions execution role.
resource "aws_iam_role" "step_functions" {
  count = var.enable_step_functions_wrapper ? 1 : 0
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

# Permissions required for Step Functions to start and monitor Glue runs.
resource "aws_iam_role_policy" "step_functions_glue" {
  count = var.enable_step_functions_wrapper ? 1 : 0
  name  = "${local.name_prefix}-sfn-glue-policy"
  role  = aws_iam_role.step_functions[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:StartJobRun",
          "glue:GetJobRun",
          "glue:GetJobRuns",
          "glue:BatchStopJobRun"
        ]
        Resource = [aws_glue_job.transform_daily.arn]
      }
    ]
  })
}

# Single-task state machine that runs Glue job synchronously.
resource "aws_sfn_state_machine" "pipeline" {
  count    = var.enable_step_functions_wrapper ? 1 : 0
  name     = "${local.name_prefix}-pipeline"
  role_arn = aws_iam_role.step_functions[0].arn

  definition = jsonencode({
    Comment = "Optional wrapper to run Glue transform job"
    StartAt = "RunTransformDaily"
    States = {
      RunTransformDaily = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.transform_daily.name
        }
        End = true
      }
    }
  })

  tags = local.common_tags
}
