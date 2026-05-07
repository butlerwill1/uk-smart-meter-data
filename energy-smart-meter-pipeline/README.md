<!-- Summary: AWS-native UK smart meter pipeline with external Bronze, Glue transforms, Athena querying, and Terraform-managed infrastructure. -->
# Energy Smart Meter Pipeline

Portfolio-ready AWS data engineering project for UK smart meter half-hourly consumption data.

The pipeline reads an external Bronze dataset, transforms it with AWS Glue (PySpark), writes Silver/Gold parquet to S3, exposes tables through Glue Catalog + Athena, and runs SQL QA checks.

## Architecture

`External S3 Bronze (read-only) -> Glue PySpark transform -> S3 Silver/Gold -> Glue Catalog -> Athena`

Components:

- `S3` for Silver, Gold, and run-log parquet data
- `AWS Glue Job` for PySpark transformations
- `AWS Glue Data Catalog` for table metadata
- `Athena` for querying and QA SQL checks
- `EventBridge Scheduler` to trigger Glue jobs
- `Lake Formation` for data permissions
- `Terraform` for infra-as-code

## Key design choices

- Bronze is external and read-only (`s3://weave.energy/smart-meter.parquet` by default).
- No copied internal Bronze layer.
- Glue job is kept defined, but daily schedule can be disabled to reduce cost.
- Partition projection is enabled on Silver/Gold/Run Log tables to avoid manual partition repair.
- Data bucket can be preserved during teardown (`preserve_data = true`).

## Repo layout

```text
energy-smart-meter-pipeline/
├── README.md
├── pyproject.toml
├── src/
│   ├── config.py
│   ├── transform_daily.py
│   ├── run_qa_checks.py
│   ├── write_run_log.py
│   ├── backfill_glue_range.py
│   ├── load_source_data.py
│   └── utils.py
├── sql/
│   ├── qa_freshness.sql
│   ├── qa_completeness.sql
│   ├── qa_uniqueness.sql
│   ├── qa_nulls.sql
│   └── qa_business_rules.sql
├── tests/
│   └── test_transform_daily.py
└── terraform/
    ├── main.tf
    ├── variables.tf
    ├── terraform.tfvars
    ├── s3.tf
    ├── glue_catalog.tf
    ├── glue_job.tf
    ├── iam.tf
    ├── athena.tf
    ├── eventbridge.tf
    ├── lakeformation.tf
    ├── step_functions.tf
    └── outputs.tf
```

## Dataset schema

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

## Outputs

Silver table:

- `silver_smart_meter_half_hourly_clean`
- partition key: `collection_date`

Gold tables:

- `gold_peak_demand_substation_day`
- `gold_avg_load_profile_day`
- partition key: `consumption_date`

Run log table:

- `pipeline_run_log`
- partition key: `run_date`

## Prerequisites

- Python `3.11`
- Terraform `>= 1.5`
- AWS CLI configured (`default` profile or your chosen profile)
- Permissions for S3, Glue, Athena, EventBridge, IAM, and Lake Formation

## Local Python setup

From `energy-smart-meter-pipeline/`:

```bash
python3.11 -m venv ../smart-meter-venv
source ../smart-meter-venv/bin/activate
pip install -e .
```

## Terraform configuration

Edit `terraform/terraform.tfvars`.

Important fields:

- `data_bucket_name`
- `athena_results_bucket_name`
- `external_source_s3_uri`
- `preserve_data`
- `enable_daily_schedule`
- `tags`

Example tags for cost attribution:

```hcl
tags = {
  Workload  = "uk-smart-meter"
  CostScope = "portfolio"
  CostOwner = "will"
}
```

Enable those tag keys in AWS Billing as cost allocation tags so they appear in Cost Explorer.

## Deploy

From `terraform/`:

```bash
terraform init
terraform plan
terraform apply
```

## Run pipeline manually

Start one Glue run for a specific date:

```bash
aws glue start-job-run \
  --job-name energy-smart-meter-pipeline-dev-transform-daily \
  --arguments '{"--run-date":"2024-02-02"}'
```

Backfill a date range sequentially (waits for each run to finish):

```bash
python src/backfill_glue_range.py \
  --job-name energy-smart-meter-pipeline-dev-transform-daily \
  --start-date 2024-02-01 \
  --end-date 2024-02-29
```

## Query with Athena

Example:

```sql
SELECT collection_date, COUNT(*) AS row_count
FROM energy_smart_meter.silver_smart_meter_half_hourly_clean
WHERE collection_date = DATE '2024-02-02'
GROUP BY 1;
```

Notes:

- Partition projection is enabled, so you should not need `MSCK REPAIR TABLE` for projected tables.
- If queries fail on column access, check Lake Formation table and column permissions.

## QA checks

SQL checks are in `sql/qa_*.sql` and include:

- Freshness
- Completeness
- Uniqueness
- Null checks
- Business rules and drift checks

Run QA script:

```bash
python src/run_qa_checks.py --run-date 2024-02-02
```

## Cost profile

Expected ongoing costs when daily schedule is disabled:

- Low baseline cost for S3 storage, Glue Catalog metadata, and Lake Formation definitions.
- Athena costs only when queries run (pay per data scanned).
- Glue ETL cost only when Glue jobs are executed.

For low-cost portfolio mode:

- Keep `enable_daily_schedule = false`
- Run Glue manually only for backfills/demo dates
- Query curated Silver/Gold subsets in Athena

## Disable daily runs while keeping Glue job

Set in `terraform.tfvars`:

```hcl
enable_daily_schedule = false
```

Apply:

```bash
cd terraform
terraform apply
```

This keeps the Glue job resource available but disables automatic daily triggering.

## Destroy infra but preserve data bucket

If `preserve_data = true`, data bucket has `prevent_destroy` and is intentionally protected.

To tear down compute/metadata while keeping data, remove protected bucket resources from state, then destroy:

```bash
terraform state rm 'aws_s3_bucket.data_preserved[0]' \
  'aws_s3_bucket_versioning.data' \
  'aws_s3_bucket_server_side_encryption_configuration.data'

terraform destroy
```

## Troubleshooting

`EntityNotFoundException` on `start-job-run`:

- Verify Glue job name from Terraform outputs.

`ConcurrentRunsExceededException`:

- Wait for prior job completion or use `backfill_glue_range.py` sequential mode.

Athena returns zero rows but files exist:

- Verify table `LOCATION` and partition path template.
- Verify date filter matches partition key and format.

`COLUMN_NOT_FOUND ... cannot be resolved or requester is not authorized`:

- This is usually Lake Formation permissions, not missing columns in file schema.
- Check table `SELECT`, `DESCRIBE`, and column wildcard grants for the querying principal.

`AccessDeniedException Required Alter/Drop` during Terraform apply/destroy:

- Grant required Lake Formation table permissions (`ALTER`, `DROP`) for the Terraform principal.
