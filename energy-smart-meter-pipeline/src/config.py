# Summary: Central configuration and CLI parsing for the smart meter pipeline.
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date, datetime


DEFAULT_PIPELINE_NAME = "uk-smart-meter-daily-pipeline"


@dataclass(frozen=True)
class PipelineConfig:
    aws_region: str
    s3_data_bucket: str
    s3_data_prefix: str
    athena_output_s3_uri: str
    glue_database: str
    raw_table_name: str
    silver_table_name: str
    gold_peak_table_name: str
    gold_load_profile_table_name: str
    run_log_table_name: str
    source_uri: str
    run_date: date
    code_version: str
    pipeline_name: str
    use_duckdb: bool

    @property
    def silver_output_uri(self) -> str:
        return f"s3://{self.s3_data_bucket}/{self.s3_data_prefix}/energy/silver/smart_meter_half_hourly_clean"

    @property
    def gold_peak_output_uri(self) -> str:
        return f"s3://{self.s3_data_bucket}/{self.s3_data_prefix}/energy/gold/gold_peak_demand_substation_day"

    @property
    def gold_load_profile_output_uri(self) -> str:
        return f"s3://{self.s3_data_bucket}/{self.s3_data_prefix}/energy/gold/gold_avg_load_profile_day"

    @property
    def run_log_output_uri(self) -> str:
        return f"s3://{self.s3_data_bucket}/{self.s3_data_prefix}/energy/meta/pipeline_run_log"


def parse_run_date(run_date_raw: str | None) -> date:
    if not run_date_raw:
        return datetime.utcnow().date()
    return datetime.strptime(run_date_raw, "%Y-%m-%d").date()


def build_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--run-date", required=False, help="Run date in YYYY-MM-DD")
    parser.add_argument("--source-uri", required=False, help="External source path (S3/local parquet)")
    parser.add_argument(
        "--local-engine",
        required=False,
        choices=["spark", "duckdb"],
        default="spark",
        help="Use duckdb for small local runs, spark for AWS mode",
    )
    return parser


def load_config(args: argparse.Namespace) -> PipelineConfig:
    run_date = parse_run_date(getattr(args, "run_date", None))
    source_uri_arg = getattr(args, "source_uri", None)
    local_engine = getattr(args, "local_engine", "spark")

    source_uri = source_uri_arg or os.getenv("SOURCE_URI", "s3://weave.energy/smart-meter.parquet")
    return PipelineConfig(
        aws_region=os.getenv("AWS_REGION", "eu-west-2"),
        s3_data_bucket=os.getenv("S3_DATA_BUCKET", "replace-me-data-bucket"),
        s3_data_prefix=os.getenv("S3_DATA_PREFIX", "portfolio"),
        athena_output_s3_uri=os.getenv(
            "ATHENA_OUTPUT_S3_URI", "s3://replace-me-athena-results-bucket/athena-results/"
        ),
        glue_database=os.getenv("GLUE_DATABASE", "energy_smart_meter"),
        raw_table_name=os.getenv("RAW_TABLE_NAME", "raw_external_smart_meter"),
        silver_table_name=os.getenv("SILVER_TABLE_NAME", "silver_smart_meter_half_hourly_clean"),
        gold_peak_table_name=os.getenv("GOLD_PEAK_TABLE_NAME", "gold_peak_demand_substation_day"),
        gold_load_profile_table_name=os.getenv(
            "GOLD_LOAD_PROFILE_TABLE_NAME", "gold_avg_load_profile_day"
        ),
        run_log_table_name=os.getenv("RUN_LOG_TABLE_NAME", "pipeline_run_log"),
        source_uri=source_uri,
        run_date=run_date,
        code_version=os.getenv("CODE_VERSION", "dev"),
        pipeline_name=os.getenv("PIPELINE_NAME", DEFAULT_PIPELINE_NAME),
        use_duckdb=local_engine == "duckdb",
    )
