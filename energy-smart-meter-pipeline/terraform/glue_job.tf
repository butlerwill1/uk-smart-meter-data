# Summary: AWS Glue ETL job, script packaging, and S3 uploads for daily PySpark transformations.
data "archive_file" "src_bundle" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/.terraform-src-bundle.zip"
}

resource "aws_s3_object" "transform_script" {
  bucket = local.data_bucket_id
  key    = "scripts/transform_daily.py"
  source = "${path.module}/../src/transform_daily.py"
  etag   = filemd5("${path.module}/../src/transform_daily.py")

  tags = local.common_tags
}

resource "aws_s3_object" "src_bundle" {
  bucket = local.data_bucket_id
  key    = "scripts/src_bundle.zip"
  source = data.archive_file.src_bundle.output_path
  etag   = data.archive_file.src_bundle.output_md5

  tags = local.common_tags
}

resource "aws_glue_job" "transform_daily" {
  name     = "${local.name_prefix}-transform-daily"
  role_arn = aws_iam_role.glue_job.arn

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

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--source-uri"                       = var.external_source_s3_uri
    "--s3-data-bucket"                   = var.data_bucket_name
    "--s3-data-prefix"                   = var.data_prefix
    "--aws-region"                       = var.aws_region
    "--extra-py-files"                   = "s3://${aws_s3_object.src_bundle.bucket}/${aws_s3_object.src_bundle.key}"
    "--TempDir"                          = "s3://${var.data_bucket_name}/scripts/tmp/"
  }

  execution_property {
    max_concurrent_runs = 1
  }

  tags = local.common_tags
}
