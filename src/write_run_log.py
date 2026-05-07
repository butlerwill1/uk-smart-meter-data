# Summary: Write one pipeline run-log record as parquet to S3 for Athena visibility.
"""Persist operational run metadata as partitioned parquet.

Each execution writes a single row into `pipeline_run_log`, partitioned by
run_date, so execution history can be queried in Athena.
"""

from __future__ import annotations

import argparse
import io
import json
from datetime import datetime, timezone

import boto3
import pyarrow as pa
import pyarrow.parquet as pq

from config import load_config
from utils import new_run_id, parse_s3_uri


def write_run_log_record(s3_uri: str, region: str, record: dict) -> str:
    """Write one run-log record parquet object and return the S3 URI."""
    table = pa.Table.from_pylist([record])
    buf = io.BytesIO()

    # Use Snappy for compact Athena-friendly parquet files.
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)

    bucket, prefix = parse_s3_uri(s3_uri)
    run_date = str(record["run_date"])
    run_id = str(record["run_id"])
    key = f"{prefix.rstrip('/')}/run_date={run_date}/run_id={run_id}.parquet"

    s3 = boto3.client("s3", region_name=region)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
    return f"s3://{bucket}/{key}"


def main() -> None:
    """CLI entrypoint for recording pipeline execution metadata."""
    parser = argparse.ArgumentParser(description="Write pipeline run log record")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD")
    parser.add_argument("--status", required=True, choices=["SUCCESS", "FAILED"])
    parser.add_argument("--started-at", required=False)
    parser.add_argument("--finished-at", required=False)
    parser.add_argument("--input-row-count", required=False, type=int, default=0)
    parser.add_argument("--silver-row-count", required=False, type=int, default=0)
    parser.add_argument("--peak-table-row-count", required=False, type=int, default=0)
    parser.add_argument("--load-profile-row-count", required=False, type=int, default=0)
    parser.add_argument("--error-message", required=False, default="")
    args = parser.parse_args()

    cfg = load_config(args)
    now = datetime.now(timezone.utc).isoformat()

    # Build a single normalized run-log row.
    record = {
        "run_id": new_run_id(),
        "pipeline_name": cfg.pipeline_name,
        "run_date": cfg.run_date.isoformat(),
        "started_at": args.started_at or now,
        "finished_at": args.finished_at or now,
        "status": args.status,
        "input_row_count": args.input_row_count,
        "silver_row_count": args.silver_row_count,
        "peak_table_row_count": args.peak_table_row_count,
        "load_profile_row_count": args.load_profile_row_count,
        "error_message": args.error_message,
        "code_version": cfg.code_version,
        "metadata": json.dumps({"region": cfg.aws_region}),
    }

    output_uri = write_run_log_record(cfg.run_log_output_uri, cfg.aws_region, record)
    print({"run_log_uri": output_uri, "run_id": record["run_id"]})


if __name__ == "__main__":
    main()
