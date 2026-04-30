# Summary: Central configuration and CLI parsing for the smart meter pipeline.
"""Pipeline configuration helpers.

This module defines:
- `PipelineConfig`: strongly typed runtime configuration.
- CLI argument parser construction shared by runnable scripts.
- Configuration resolution order (CLI -> environment variable -> default).

Every script loads configuration through this module so behavior stays
consistent between local runs and AWS Glue executions.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date, datetime


DEFAULT_PIPELINE_NAME = "uk-smart-meter-daily-pipeline"


@dataclass(frozen=True)
class PipelineConfig:
    """Container for all pipeline runtime settings.

    Values are populated from command-line arguments and environment
    variables and then passed into pipeline modules.
    """

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
        """S3 base URI for silver outputs."""
        return f"s3://{self.s3_data_bucket}/{self.s3_data_prefix}/energy/silver/smart_meter_half_hourly_clean"

    @property
    def gold_peak_output_uri(self) -> str:
        """S3 base URI for gold peak-demand outputs."""
        return f"s3://{self.s3_data_bucket}/{self.s3_data_prefix}/energy/gold/gold_peak_demand_substation_day"

    @property
    def gold_load_profile_output_uri(self) -> str:
        """S3 base URI for gold load-profile outputs."""
        return f"s3://{self.s3_data_bucket}/{self.s3_data_prefix}/energy/gold/gold_avg_load_profile_day"

    @property
    def run_log_output_uri(self) -> str:
        """S3 base URI for pipeline run logs."""
        return f"s3://{self.s3_data_bucket}/{self.s3_data_prefix}/energy/meta/pipeline_run_log"


def parse_run_date(run_date_raw: str | None) -> date:
    """Parse a run-date string into a date object.

    Special values `AUTO` and `TODAY` map to current UTC date to support
    scheduled runs that do not provide an explicit date.
    """
    if not run_date_raw or run_date_raw.upper() in {"AUTO", "TODAY"}:
        return datetime.utcnow().date()
    return datetime.strptime(run_date_raw, "%Y-%m-%d").date()


def build_parser(description: str) -> argparse.ArgumentParser:
    """Build a shared CLI parser used by executable scripts."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--run-date", required=False, help="Run date in YYYY-MM-DD")
    parser.add_argument("--source-uri", required=False, help="External source path (S3/local parquet)")
    parser.add_argument("--s3-data-bucket", required=False, help="Target S3 data bucket")
    parser.add_argument("--s3-data-prefix", required=False, help="Target S3 data prefix")
    parser.add_argument("--aws-region", required=False, help="AWS region")
    parser.add_argument("--glue-database", required=False, help="Glue database")
    parser.add_argument("--athena-output-s3-uri", required=False, help="Athena output S3 URI")
    parser.add_argument("--pipeline-name", required=False, help="Pipeline name")
    parser.add_argument("--code-version", required=False, help="Code version")
    parser.add_argument(
        "--local-engine",
        required=False,
        choices=["spark", "duckdb"],
        default="spark",
        help="Use duckdb for small local runs, spark for AWS mode",
    )
    return parser


def _arg_or_env(arg_value: str | None, env_name: str, default: str) -> str:
    """Return CLI value when provided, otherwise environment/default fallback."""
    return arg_value or os.getenv(env_name, default)


def load_config(args: argparse.Namespace) -> PipelineConfig:
    """Resolve and return full runtime configuration for a script execution."""
    run_date = parse_run_date(getattr(args, "run_date", None))
    source_uri = _arg_or_env(getattr(args, "source_uri", None), "SOURCE_URI", "s3://weave.energy/smart-meter.parquet")

    return PipelineConfig(
        aws_region=_arg_or_env(getattr(args, "aws_region", None), "AWS_REGION", "eu-west-2"),
        s3_data_bucket=_arg_or_env(getattr(args, "s3_data_bucket", None), "S3_DATA_BUCKET", "replace-me-data-bucket"),
        s3_data_prefix=_arg_or_env(getattr(args, "s3_data_prefix", None), "S3_DATA_PREFIX", "portfolio"),
        athena_output_s3_uri=_arg_or_env(
            getattr(args, "athena_output_s3_uri", None),
            "ATHENA_OUTPUT_S3_URI",
            "s3://replace-me-athena-results-bucket/athena-results/",
        ),
        glue_database=_arg_or_env(getattr(args, "glue_database", None), "GLUE_DATABASE", "energy_smart_meter"),
        raw_table_name=os.getenv("RAW_TABLE_NAME", "raw_external_smart_meter"),
        silver_table_name=os.getenv("SILVER_TABLE_NAME", "silver_smart_meter_half_hourly_clean"),
        gold_peak_table_name=os.getenv("GOLD_PEAK_TABLE_NAME", "gold_peak_demand_substation_day"),
        gold_load_profile_table_name=os.getenv("GOLD_LOAD_PROFILE_TABLE_NAME", "gold_avg_load_profile_day"),
        run_log_table_name=os.getenv("RUN_LOG_TABLE_NAME", "pipeline_run_log"),
        source_uri=source_uri,
        run_date=run_date,
        code_version=_arg_or_env(getattr(args, "code_version", None), "CODE_VERSION", "dev"),
        pipeline_name=_arg_or_env(getattr(args, "pipeline_name", None), "PIPELINE_NAME", DEFAULT_PIPELINE_NAME),
        use_duckdb=getattr(args, "local_engine", "spark") == "duckdb",
    )
