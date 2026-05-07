# Summary: Run AWS Glue backfills sequentially across a date range, waiting for each day to finish before starting the next.
"""Sequential Glue backfill runner.

This script starts one Glue job run per date in an inclusive date range and waits
for each run to reach a terminal state before triggering the next date.

Default behavior stops on first failure. Use --continue-on-failure to keep going.

Example:
    python src/backfill_glue_range.py \
      --job-name energy-smart-meter-pipeline-dev-transform-daily \
      --start-date 2024-09-01 \
      --end-date 2024-09-07 \
      --region eu-west-2 \
      --poll-seconds 30
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import date, datetime, timedelta

import boto3
from botocore.exceptions import ClientError


TERMINAL_STATES = {"SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT", "ERROR"}
ACTIVE_STATES = {"STARTING", "RUNNING", "STOPPING", "WAITING"}


def parse_date(value: str) -> date:
    """Parse YYYY-MM-DD into a date object."""
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_dates(start_date: date, end_date: date):
    """Yield dates from start_date to end_date inclusive."""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def wait_for_completion(glue_client, job_name: str, run_id: str, poll_seconds: int) -> dict:
    """Poll Glue until job run reaches a terminal state, then return JobRun payload."""
    last_state = None

    while True:
        response = glue_client.get_job_run(
            JobName=job_name,
            RunId=run_id,
            PredecessorsIncluded=False,
        )
        job_run = response["JobRun"]
        state = job_run["JobRunState"]

        if state != last_state:
            print({"run_id": run_id, "state": state})
            last_state = state

        if state in TERMINAL_STATES:
            return job_run

        time.sleep(poll_seconds)


def wait_for_job_slot(glue_client, job_name: str, poll_seconds: int) -> None:
    """Wait until the Glue job has no active runs before starting a new one."""
    last_active_ids = None

    while True:
        response = glue_client.get_job_runs(JobName=job_name, MaxResults=25)
        active_runs = [
            run["Id"]
            for run in response.get("JobRuns", [])
            if run.get("JobRunState") in ACTIVE_STATES
        ]

        if not active_runs:
            return

        active_ids = sorted(active_runs)
        if active_ids != last_active_ids:
            print(
                {
                    "event": "waiting_for_available_job_slot",
                    "job_name": job_name,
                    "active_run_ids": active_ids,
                    "poll_seconds": poll_seconds,
                }
            )
            last_active_ids = active_ids

        time.sleep(poll_seconds)


def start_job_run_with_retry(
    glue_client,
    job_name: str,
    run_date_str: str,
    retry_seconds: int,
    max_retries: int,
) -> str:
    """Start a Glue run and retry when job concurrency limit is temporarily exceeded."""
    attempt = 0
    while True:
        try:
            response = glue_client.start_job_run(
                JobName=job_name,
                Arguments={"--run-date": run_date_str},
            )
            return response["JobRunId"]
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code != "ConcurrentRunsExceededException":
                raise

            attempt += 1
            if attempt > max_retries:
                raise

            print(
                {
                    "event": "start_retry_wait",
                    "run_date": run_date_str,
                    "attempt": attempt,
                    "retry_seconds": retry_seconds,
                    "reason": "ConcurrentRunsExceededException",
                }
            )
            time.sleep(retry_seconds)


def main() -> None:
    """CLI entrypoint for sequential daily Glue backfills."""
    parser = argparse.ArgumentParser(description="Run sequential AWS Glue backfills by date range")
    parser.add_argument("--job-name", required=True, help="Glue job name")
    parser.add_argument("--start-date", required=True, help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Backfill end date (YYYY-MM-DD)")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "eu-west-2"), help="AWS region")
    parser.add_argument("--poll-seconds", type=int, default=30, help="Polling interval for Glue run status")
    parser.add_argument(
        "--start-retry-seconds",
        type=int,
        default=30,
        help="Wait time between start retries when Glue concurrency is exceeded",
    )
    parser.add_argument(
        "--max-start-retries",
        type=int,
        default=20,
        help="Maximum retries when start-job-run hits concurrency limits",
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Continue processing remaining dates even if a date fails",
    )
    args = parser.parse_args()

    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    if end_date < start_date:
        raise SystemExit("end-date must be on or after start-date")

    glue = boto3.client("glue", region_name=args.region)
    failures: list[dict] = []

    for run_date in iter_dates(start_date, end_date):
        run_date_str = run_date.isoformat()
        print({"event": "start_date_run", "run_date": run_date_str, "job_name": args.job_name})

        # Ensure no other run of this job is currently active (including scheduler-triggered runs).
        wait_for_job_slot(
            glue_client=glue,
            job_name=args.job_name,
            poll_seconds=args.poll_seconds,
        )

        run_id = start_job_run_with_retry(
            glue_client=glue,
            job_name=args.job_name,
            run_date_str=run_date_str,
            retry_seconds=args.start_retry_seconds,
            max_retries=args.max_start_retries,
        )
        print({"event": "job_started", "run_date": run_date_str, "run_id": run_id})

        result = wait_for_completion(
            glue_client=glue,
            job_name=args.job_name,
            run_id=run_id,
            poll_seconds=args.poll_seconds,
        )

        state = result["JobRunState"]
        summary = {
            "event": "job_finished",
            "run_date": run_date_str,
            "run_id": run_id,
            "state": state,
            "execution_time_seconds": result.get("ExecutionTime"),
            "error_message": result.get("ErrorMessage"),
        }
        print(summary)

        if state != "SUCCEEDED":
            failures.append(summary)
            if not args.continue_on_failure:
                break

    if failures:
        print({"event": "backfill_complete", "status": "FAILED", "failure_count": len(failures), "failures": failures})
        raise SystemExit(1)

    print({"event": "backfill_complete", "status": "SUCCEEDED"})


if __name__ == "__main__":
    main()
