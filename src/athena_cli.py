# Summary: Mini CLI to run Athena SQL from inline text or SQL files and print tabular results.
"""Run Athena queries from the command line.

Examples:
- Inline query:
  python src/athena_cli.py --query "SELECT 1" --database energy_smart_meter --output-s3-uri s3://bucket/athena-results/

- SQL file query:
  python src/athena_cli.py --sql-file sql/insights/01_date_coverage.sql --database energy_smart_meter --output-s3-uri s3://bucket/athena-results/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import boto3

from athena_utils import fetch_rows, render_table, run_query, to_result
from config import load_config


def _build_parser() -> argparse.ArgumentParser:
    """Create CLI parser for Athena query execution."""
    parser = argparse.ArgumentParser(description="Run an Athena SQL query and print results")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query", help="Inline SQL query to execute")
    group.add_argument("--sql-file", help="Path to SQL file to execute")

    parser.add_argument("--database", help="Glue/Athena database name (defaults to config)")
    parser.add_argument("--workgroup", default="energy-smart-meter-pipeline-dev-athena", help="Athena workgroup")
    parser.add_argument("--output-s3-uri", help="Athena query output S3 URI")
    parser.add_argument("--aws-region", help="AWS region")
    parser.add_argument("--max-rows", type=int, default=100, help="Maximum rows to print")
    parser.add_argument("--save-json", help="Optional path to save rows/metadata as JSON")
    return parser


def _resolve_query(args: argparse.Namespace) -> str:
    """Resolve query text from inline SQL or file input."""
    if args.query:
        return args.query
    return Path(args.sql_file).read_text(encoding="utf-8")


def main() -> None:
    """CLI entrypoint for interactive Athena querying."""
    parser = _build_parser()
    args = parser.parse_args()
    cfg = load_config(args)

    database = args.database or cfg.glue_database
    output_s3_uri = args.output_s3_uri or cfg.athena_output_s3_uri

    if "replace-me-" in output_s3_uri:
        raise SystemExit("Provide --output-s3-uri or set ATHENA_OUTPUT_S3_URI to a real S3 location.")

    query = _resolve_query(args)
    athena = boto3.client("athena", region_name=cfg.aws_region)

    qid, status = run_query(
        athena,
        query=query,
        database=database,
        output_location=output_s3_uri,
        workgroup=args.workgroup,
    )

    state = status["QueryExecution"]["Status"]["State"]
    if state != "SUCCEEDED":
        reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
        raise SystemExit(f"Query failed with state={state}: {reason}")

    columns, rows = fetch_rows(athena, query_execution_id=qid, max_rows=args.max_rows)
    result = to_result(qid, status, columns, rows)

    print(f"query_execution_id={result.query_execution_id}")
    print(f"state={result.state}")
    print(render_table(result.columns, result.rows))

    if args.save_json:
        payload = {
            "query_execution_id": result.query_execution_id,
            "state": result.state,
            "columns": result.columns,
            "rows": result.rows,
        }
        Path(args.save_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"saved_json={args.save_json}")


if __name__ == "__main__":
    main()
