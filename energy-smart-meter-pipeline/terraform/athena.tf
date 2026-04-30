# Summary: Athena workgroup configured to write query outputs to dedicated S3 location.
# Workgroup settings are enforced so all queries consistently use project output location.

resource "aws_athena_workgroup" "smart_meter" {
  name = "${local.name_prefix}-athena"

  configuration {
    result_configuration {
      # Centralized query output destination.
      output_location = local.athena_output_location
    }

    # Enforce workgroup-level settings for consistent behavior.
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
  }

  state = "ENABLED"
  tags  = local.common_tags
}
