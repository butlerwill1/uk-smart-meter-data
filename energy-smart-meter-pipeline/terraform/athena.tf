# Summary: Athena workgroup configured to write query outputs to dedicated S3 location.
resource "aws_athena_workgroup" "smart_meter" {
  name = "${local.name_prefix}-athena"

  configuration {
    result_configuration {
      output_location = local.athena_output_location
    }

    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
  }

  state = "ENABLED"
  tags  = local.common_tags
}
