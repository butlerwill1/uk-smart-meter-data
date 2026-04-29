<!-- Summary: Portfolio-ready AWS data pipeline for UK smart meter half-hourly consumption analytics with external Bronze data. -->
# Energy Smart Meter Pipeline

A portfolio-ready AWS-native data engineering project for UK smart meter half-hourly consumption data.

The pipeline treats an external source dataset as the Bronze layer (read-only), transforms to Silver and Gold in your own S3 bucket, exposes data through Glue Catalog and Athena, and runs SQL QA checks designed for LLM/data QA agents.

## Why this project is useful

- Uses lightweight AWS-native orchestration (EventBridge Scheduler + optional Step Functions), not Airflow.
- Uses Glue + Athena over S3 parquet for practical analytics architecture.
- Uses read-only external Bronze data to avoid redundant copy/storage cost and simplify the portfolio setup.
- Implements realistic QA checks for freshness, completeness, uniqueness, nulls, business constraints, and drift thresholds.
- Demonstrates idempotent daily/backfill processing by overwriting only date partitions in Silver/Gold.

## Architecture

- Bronze: external read-only parquet dataset (example: `s3://weave.energy/smart-meter.parquet`)
- Silver/Gold/Run Log storage: S3 parquet in your data bucket
- Metadata: AWS Glue Data Catalog external tables
- Query engine: Athena
- Scheduling: EventBridge Scheduler (daily cron/rate + optional one-off backfill)
- Orchestration visibility: optional Step Functions
- Infrastructure as code: Terraform
- Transform engine: Python + PySpark (optional DuckDB fallback for local small runs)

Pipeline:

`External Source (Bronze) -> Silver -> Gold -> QA checks -> Run log`

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

Each row is a half-hourly reading for a feeder connected to a secondary substation.

## Assumptions

- External Bronze dataset is stable and accessible from your AWS environment.
- Pipeline does not modify external Bronze and does not copy Bronze into your S3 bucket.

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

## Pipeline logic

### 1) Load external source (Bronze, read-only)

Run:

```bash
python src/load_source_data.py --run-date 2024-02-12 --source-uri s3://weave.energy/smart-meter.parquet
```

Behavior:

- Reads external parquet/GeoParquet directly.
- Filters by `run_date` from `data_collection_log_timestamp`.
- Does not write Bronze data to your S3 bucket.

### 2) Build Silver + Gold

Run:

```bash
python src/transform_daily.py --run-date 2024-02-12 --source-uri s3://weave.energy/smart-meter.parquet
```

Filtering behavior:

- Run-date filter is applied while reading the external source dataset.

Silver columns include:

- `collection_date`
- `hour_of_day`
- `minute_of_hour`
- `half_hour_slot`
- `day_of_week`
- `is_weekend`
- `composite_feeder_id`
- `consumption_per_active_device`

Silver output:

- `s3://<bucket>/<prefix>/energy/silver/smart_meter_half_hourly_clean/collection_date=YYYY-MM-DD/`

Gold outputs:

- `gold_peak_demand_substation_day`
- `gold_avg_load_profile_day`

Gold output paths:

- `s3://<bucket>/<prefix>/energy/gold/gold_peak_demand_substation_day/consumption_date=YYYY-MM-DD/`
- `s3://<bucket>/<prefix>/energy/gold/gold_avg_load_profile_day/consumption_date=YYYY-MM-DD/`

### 3) Run QA checks (Athena)

Run:

```bash
python src/run_qa_checks.py --run-date 2024-02-12
```

Executes SQL files in `sql/` for:

- Freshness
- Completeness (48 slots + timestamp coverage)
- Uniqueness
- Null checks
- Business rules + distribution drift checks

### 4) Write run log

Run:

```bash
python src/write_run_log.py \
  --run-date 2024-02-12 \
  --status SUCCESS \
  --input-row-count 100000 \
  --silver-row-count 100000 \
  --peak-table-row-count 1200 \
  --load-profile-row-count 48
```

Writes one parquet row per run to:

- `s3://<bucket>/<prefix>/energy/meta/pipeline_run_log/run_date=YYYY-MM-DD/`

## Backfill and idempotency

Backfill any day:

```bash
python src/transform_daily.py --run-date 2024-02-12 --source-uri s3://weave.energy/smart-meter.parquet
```

Idempotency behavior:

- Re-running the same date overwrites only that date partitions in Silver/Gold.
- Unrelated dates are not rewritten.
- External Bronze source is never modified.

## Optional local mode (DuckDB)

For small local test runs:

```bash
python src/transform_daily.py --run-date 2024-02-12 --source-uri ./data/source/*.parquet --local-engine duckdb
```

AWS/Athena remains the primary target for production-like execution.

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

enable_step_functions      = true
load_source_lambda_arn     = "arn:aws:lambda:eu-west-2:123456789012:function:smart-meter-load-source"
transform_lambda_arn       = "arn:aws:lambda:eu-west-2:123456789012:function:smart-meter-transform"
qa_lambda_arn              = "arn:aws:lambda:eu-west-2:123456789012:function:smart-meter-qa"
run_log_lambda_arn         = "arn:aws:lambda:eu-west-2:123456789012:function:smart-meter-log"

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

### 3) Destroy compute while preserving S3 data

With `preserve_data = true`, Terraform applies `prevent_destroy` on the data bucket.

To remove compute/orchestration/metadata resources while preserving data storage:

```bash
terraform destroy
```

If you explicitly want data bucket deletion, set:

```hcl
preserve_data = false
```

Then run `terraform apply` and `terraform destroy`.

## Glue and Athena tables

- External Bronze table: `raw_external_smart_meter` (read-only source location)
- Silver table: `silver_smart_meter_half_hourly_clean`
- Gold tables:
  - `gold_peak_demand_substation_day`
  - `gold_avg_load_profile_day`
- Run log table: `pipeline_run_log`

## Athena querying

```sql
SELECT *
FROM energy_smart_meter.gold_peak_demand_substation_day
WHERE consumption_date = DATE '2024-02-12'
ORDER BY peak_consumption DESC
LIMIT 20;
```

```sql
SELECT hour_of_day, minute_of_hour, avg_consumption
FROM energy_smart_meter.gold_avg_load_profile_day
WHERE consumption_date = DATE '2024-02-12'
ORDER BY half_hour_slot;
```

## QA checks for LLM/data QA agents

SQL checks in `sql/qa_*.sql` are designed for agent-driven Athena execution and PASS/FAIL interpretation.

Included validations:

- Freshness: data exists for `run_date`
- Completeness: 48 half-hour slots and full timestamp coverage
- Uniqueness: one row per key in each gold table
- Nulls: required columns populated
- Business + drift:
  - `peak_consumption <= daily_total_consumption`
  - `aggregated_device_count_active > 0`
  - `total_consumption_active_import >= 0`
  - `consumption_per_active_device >= 0`
  - row count change <= 20% vs previous available date
  - average consumption change <= 30% vs previous available date

## Quick start

```bash
python -m venv smart-meter-venv
source smart-meter-venv/bin/activate
pip install -e .[dev]

export AWS_REGION=eu-west-2
export SOURCE_URI=s3://weave.energy/smart-meter.parquet
export S3_DATA_BUCKET=my-smart-meter-data-bucket
export S3_DATA_PREFIX=portfolio
export ATHENA_OUTPUT_S3_URI=s3://my-smart-meter-athena-results/athena-results/
export GLUE_DATABASE=energy_smart_meter

python src/load_source_data.py --run-date 2024-02-12
python src/transform_daily.py --run-date 2024-02-12
python src/run_qa_checks.py --run-date 2024-02-12
python src/write_run_log.py --run-date 2024-02-12 --status SUCCESS
```
