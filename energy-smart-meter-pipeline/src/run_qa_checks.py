# Summary: Execute Athena SQL QA checks and emit pass/fail results for a run date.
from __future__ import annotations

import argparse
import time
from pathlib import Path

import boto3

from config import load_config


SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def start_and_wait_query(
    athena_client,
    query: str,
    database: str,
    output_location: str,
    poll_seconds: int = 2,
) -> dict:
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
    text = sql_path.read_text(encoding="utf-8")
    return text.format(run_date=run_date, glue_database=database)


def run_checks(run_date: str, region: str, database: str, output_location: str) -> list[dict]:
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
    parser = argparse.ArgumentParser(description="Run Athena QA checks for a run date")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD")
    parser.add_argument("--local-engine", required=False, default="spark")
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
