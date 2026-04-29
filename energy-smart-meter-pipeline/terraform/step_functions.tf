# Summary: Optional Step Functions workflow chaining source load, transform, QA, and run-log steps.
resource "aws_sfn_state_machine" "pipeline" {
  count    = var.enable_step_functions ? 1 : 0
  name     = "${local.name_prefix}-pipeline"
  role_arn = aws_iam_role.step_functions[0].arn

  definition = jsonencode({
    Comment = "Smart meter daily pipeline"
    StartAt = "LoadSourceData"
    States = {
      LoadSourceData = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.load_source_lambda_arn
          "Payload.$"  = "$"
        }
        ResultPath = "$.load_source"
        Next       = "TransformDaily"
      }
      TransformDaily = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.transform_lambda_arn
          "Payload.$"  = "$"
        }
        ResultPath = "$.transform"
        Next       = "RunQaChecks"
      }
      RunQaChecks = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.qa_lambda_arn
          "Payload.$"  = "$"
        }
        ResultPath = "$.qa"
        Next       = "WriteRunLog"
      }
      WriteRunLog = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.run_log_lambda_arn
          "Payload.$"  = "$"
        }
        End = true
      }
    }
  })

  tags = local.common_tags
}
