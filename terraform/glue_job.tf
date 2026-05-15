# Summary: AWS Glue ETL job, script packaging, and S3 uploads for daily PySpark transformations.
# Flow in this file:
# 1) Zip reusable source modules.
# 2) Upload transform entrypoint and dependency bundle to S3.
# 3) Define Glue job pointing to uploaded script and runtime args.

# Package the local src directory into a zip artifact for --extra-py-files.
data "archive_file" "src_bundle" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/.terraform-src-bundle.zip"
}

# Upload the Glue entrypoint script.
resource "aws_s3_object" "transform_script" {
  bucket = local.data_bucket_id
  key    = "scripts/transform_daily.py"
  source = "${path.module}/../src/transform_daily.py"

  # Ensure script updates trigger object replacement when content changes.
  etag = filemd5("${path.module}/../src/transform_daily.py")

  tags = local.common_tags
}

# Upload shared source bundle used by import statements in the job.
resource "aws_s3_object" "src_bundle" {
  bucket = local.data_bucket_id
  key    = "scripts/src_bundle.zip"
  source = data.archive_file.src_bundle.output_path

  # Ensure bundle updates are detected by Terraform.
  etag = data.archive_file.src_bundle.output_md5

  tags = local.common_tags
}

# Glue Spark job used for production transformation runs.
resource "aws_glue_job" "transform_daily" {
  name     = "${local.name_prefix}-transform-daily"
  role_arn = aws_iam_role.glue_job.arn

  # Glue runtime and cost-control settings.
  glue_version      = "4.0"
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_number_of_workers
  max_retries       = 0
  timeout           = 60

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_object.transform_script.bucket}/${aws_s3_object.transform_script.key}"
    python_version  = "3"
  }

  # Runtime arguments passed to script entrypoint.
  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--source-uri"                       = var.external_source_s3_uri
    "--s3-data-bucket"                   = var.data_bucket_name
    "--s3-data-prefix"                   = var.data_prefix
    "--aws-region"                       = var.aws_region
    "--zscore-threshold"                 = "3.0"
    "--extra-py-files"                   = "s3://${aws_s3_object.src_bundle.bucket}/${aws_s3_object.src_bundle.key}"
    "--TempDir"                          = "s3://${var.data_bucket_name}/scripts/tmp/"
  }

  # Prevent overlapping runs for the same job definition.
  execution_property {
    max_concurrent_runs = 1
  }

  tags = local.common_tags
}
