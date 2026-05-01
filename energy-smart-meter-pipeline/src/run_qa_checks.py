# Summary: Execute Athena SQL QA checks and emit pass/fail results for a run date.
"""Athena QA runner for data quality checks.

This module executes SQL checks from `sql/qa_*.sql`, waits for each query to
finish, and returns structured status records that can be interpreted by
automation or an LLM/data QA agent.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import boto3

from config import load_config


# Central location for SQL QA templates.
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def start_and_wait_query(
    athena_client,
    query: str,
    database: str,
    output_location: str,
    poll_seconds: int = 2,
) -> dict:
    """Submit an Athena query and block until it reaches a terminal state."""
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": output_location},
    )
    qid = response["QueryExecutionId"]

    while True:
        status = athena_client.get_query_execution(QueryExecutionId=qid)
        state = status["QueryExecution"]["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return status
        time.sleep(poll_seconds)


def materialize_sql(sql_path: Path, run_date: str, database: str) -> str:
    """Render an SQL template with runtime values."""
    text = sql_path.read_text(encoding="utf-8")
    return text.format(run_date=run_date, glue_database=database)


def run_checks(run_date: str, region: str, database: str, output_location: str) -> list[dict]:
    """Execute all configured QA checks and return per-check status details."""
    athena = boto3.client("athena", region_name=region)
    checks = [
        "qa_freshness.sql",
        "qa_completeness.sql",
        "qa_uniqueness.sql",
        "qa_nulls.sql",
        "qa_business_rules.sql",
    ]

    results: list[dict] = []
    for check_file in checks:
        query = materialize_sql(SQL_DIR / check_file, run_date, database)
        status = start_and_wait_query(athena, query, database, output_location)
        final_state = status["QueryExecution"]["Status"]["State"]
        reason = status["QueryExecution"]["Status"].get("StateChangeReason")
        results.append(
            {
                "check": check_file,
                "state": final_state,
                "reason": reason,
                "query_execution_id": status["QueryExecution"]["QueryExecutionId"],
            }
        )
    return results


def main() -> None:
    """CLI entrypoint to run all QA checks for one run date."""
    parser = argparse.ArgumentParser(description="Run Athena QA checks for a run date")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD")
    args = parser.parse_args()
    cfg = load_config(args)

    results = run_checks(
        run_date=cfg.run_date.isoformat(),
        region=cfg.aws_region,
        database=cfg.glue_database,
        output_location=cfg.athena_output_s3_uri,
    )

    failed = [r for r in results if r["state"] != "SUCCEEDED"]
    print({"results": results, "failed_count": len(failed)})
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
