<!-- Summary: Portfolio-ready AWS data pipeline for UK smart meter half-hourly consumption analytics with AWS Glue execution. -->
# Energy Smart Meter Pipeline

A portfolio-ready AWS-native data engineering project for UK smart meter half-hourly consumption data.

The pipeline treats an external source dataset as the Bronze layer (read-only), runs PySpark transformations in AWS Glue jobs, writes Silver and Gold parquet data to your S3 bucket, exposes data through Glue Catalog and Athena, and keeps QA/run-log workflows for agent-driven validation.

## Why this project is useful

- Uses AWS Glue jobs for serverless PySpark execution.
- Uses EventBridge Scheduler to trigger Glue directly (daily and one-off backfills).
- Avoids copying Bronze data, reducing storage cost and complexity.
- Uses Glue + Athena over S3 parquet for a realistic analytics pattern.
- Preserves idempotent daily processing by overwriting only target date partitions.

## Execution environment for PySpark

PySpark transformations run in **AWS Glue** (production target).

- Main transform script: `src/transform_daily.py`
- Uploaded by Terraform to:
  - `s3://<data_bucket>/scripts/transform_daily.py`
- Glue job runs that script using Glue Spark runtime and writes Silver/Gold partitions to your data bucket.
- Script accepts `--run-date YYYY-MM-DD`.

Local fallback remains available for development with standard `SparkSession.builder`.

## Architecture

- Bronze: external read-only parquet dataset (example: `s3://weave.energy/smart-meter.parquet`)
- Transform compute: AWS Glue job (`transform_daily`)
- Silver/Gold/Run Log storage: S3 parquet in your data bucket
- Metadata: AWS Glue Data Catalog external tables
- Query engine: Athena
- Scheduling: EventBridge Scheduler -> Glue `StartJobRun`
- Optional orchestration visibility: Step Functions wrapper around Glue job (disabled by default)
- Infrastructure as code: Terraform

Pipeline:

`External Source (Bronze) -> AWS Glue PySpark Transform -> Silver -> Gold -> QA checks -> Run log`

## Dataset shape

Expected source columns:

- `dataset_id`
- `dno_alias`
- `aggregated_device_count_active`
- `total_consumption_active_import`
- `data_collection_log_timestamp`
- `geometry`
- `secondary_substation_unique_id`
- `lv_feeder_unique_id`
- `bbox`

## Assumptions

- External Bronze dataset is stable and accessible from your AWS account/network context.
- Bronze is read-only and never modified by this pipeline.

## Project layout

```text
energy-smart-meter-pipeline/
├── README.md
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── s3.tf
│   ├── glue_catalog.tf
│   ├── glue_job.tf
│   ├── athena.tf
│   ├── iam.tf
│   ├── eventbridge.tf
│   └── step_functions.tf
├── src/
│   ├── config.py
│   ├── load_source_data.py
│   ├── transform_daily.py
│   ├── run_qa_checks.py
│   ├── write_run_log.py
│   └── utils.py
├── sql/
│   ├── create_raw_table.sql
│   ├── create_gold_peak_demand_substation_day.sql
│   ├── create_gold_avg_load_profile_day.sql
│   ├── qa_freshness.sql
│   ├── qa_uniqueness.sql
│   ├── qa_completeness.sql
│   ├── qa_nulls.sql
│   └── qa_business_rules.sql
├── tests/
│   └── test_transform_daily.py
└── pyproject.toml
```

## Terraform deployment

### 1) Configure variables

Create `terraform.tfvars` in `terraform/`:

```hcl
aws_region                 = "eu-west-2"
project_name               = "energy-smart-meter-pipeline"
environment                = "dev"
external_source_s3_uri     = "s3://weave.energy/smart-meter.parquet"
data_bucket_name           = "my-smart-meter-data-bucket"
athena_results_bucket_name = "my-smart-meter-athena-results"
data_prefix                = "portfolio"
preserve_data              = true

glue_worker_type           = "G.1X"
glue_number_of_workers     = 2
enable_step_functions_wrapper = false

daily_schedule_expression  = "cron(0 2 * * ? *)"
scheduler_timezone         = "Europe/London"

enable_backfill_one_off      = false
backfill_schedule_expression = "at(2026-01-15T01:00:00)"
backfill_run_date            = "2026-01-14"
```

### 2) Apply

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Terraform provisions:

- Glue job for `transform_daily.py`
- S3 script upload (`scripts/transform_daily.py`, `scripts/src_bundle.zip`)
- EventBridge Scheduler daily trigger for Glue `StartJobRun`
- Optional one-off backfill schedule with explicit `--run-date`
- Glue Catalog + Athena resources

### 3) Triggering behavior

- Daily schedule starts Glue job with `--run-date AUTO` (script resolves to current UTC date)
- One-off backfill schedule starts Glue job with `--run-date <backfill_run_date>`

## Running one-day backfill manually

Direct Glue CLI example:

```bash
aws glue start-job-run \
  --job-name <transform_glue_job_name> \
  --arguments '{"--run-date":"2024-02-12"}'
```

Local development fallback:

```bash
python src/transform_daily.py --run-date 2024-02-12 --source-uri ./data/source/*.parquet
```

## Logging

- Primary transform logs: AWS Glue job logs in CloudWatch
- Operational run metadata: `pipeline_run_log` parquet table in S3/Athena (unchanged)

## Idempotency

- Re-running same date overwrites only Silver/Gold partitions for that date.
- Unrelated dates are not rewritten.
- External Bronze source is never modified.

## Glue and Athena tables

- External Bronze table: `raw_external_smart_meter`
- Silver table: `silver_smart_meter_half_hourly_clean`
- Gold tables:
  - `gold_peak_demand_substation_day`
  - `gold_avg_load_profile_day`
- Run log table: `pipeline_run_log`

## QA checks for LLM/data QA agents

QA SQL and run-log workflows are unchanged.

- Freshness, completeness, uniqueness, null, business-rule, and drift checks
- Athena-executable `qa_*.sql` files
- PASS/FAIL-friendly output structure

## Destroy compute while preserving data

With `preserve_data = true`, Terraform keeps the data bucket protected using `prevent_destroy`.

```bash
terraform destroy
```

This removes compute/orchestration/metadata resources while preserving stored parquet data.
