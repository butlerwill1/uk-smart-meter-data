# Summary: Shared Athena query helpers for running SQL, waiting for completion, and fetching tabular results.
"""Utilities for Athena query execution.

This module provides small, reusable helpers to:
- start Athena queries,
- wait for terminal status,
- fetch result rows,
- render a simple text table for CLI output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import time


@dataclass
class AthenaResult:
    """Container for Athena query metadata and rows."""

    query_execution_id: str
    state: str
    columns: list[str]
    rows: list[dict[str, str | None]]
    state_change_reason: str | None = None


def run_query(
    athena_client: Any,
    *,
    query: str,
    database: str,
    output_location: str,
    workgroup: str | None = None,
    poll_seconds: int = 2,
) -> tuple[str, dict[str, Any]]:
    """Start a query and wait until it reaches a terminal state."""
    params: dict[str, Any] = {
        "QueryString": query,
        "QueryExecutionContext": {"Database": database},
        "ResultConfiguration": {"OutputLocation": output_location},
    }
    if workgroup:
        params["WorkGroup"] = workgroup

    start = athena_client.start_query_execution(**params)
    qid = start["QueryExecutionId"]

    while True:
        status = athena_client.get_query_execution(QueryExecutionId=qid)
        state = status["QueryExecution"]["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return qid, status
        time.sleep(poll_seconds)


def fetch_rows(athena_client: Any, *, query_execution_id: str, max_rows: int = 200) -> tuple[list[str], list[dict[str, str | None]]]:
    """Fetch query results from Athena and return (columns, rows)."""
    paginator_token: str | None = None
    columns: list[str] = []
    rows: list[dict[str, str | None]] = []
    first_page = True

    while len(rows) < max_rows:
        kwargs: dict[str, Any] = {
            "QueryExecutionId": query_execution_id,
            "MaxResults": min(1000, max_rows + 1),
        }
        if paginator_token:
            kwargs["NextToken"] = paginator_token

        response = athena_client.get_query_results(**kwargs)
        result_set = response["ResultSet"]
        metadata = result_set["ResultSetMetadata"]["ColumnInfo"]
        data_rows = result_set["Rows"]

        if not columns:
            columns = [col["Name"] for col in metadata]

        # Athena includes header row as first row on first page.
        start_idx = 1 if first_page else 0
        for row in data_rows[start_idx:]:
            if len(rows) >= max_rows:
                break
            values = [cell.get("VarCharValue") for cell in row.get("Data", [])]
            values += [None] * (len(columns) - len(values))
            rows.append(dict(zip(columns, values)))

        first_page = False
        paginator_token = response.get("NextToken")
        if not paginator_token:
            break

    return columns, rows


def to_result(query_execution_id: str, status: dict[str, Any], columns: list[str], rows: list[dict[str, str | None]]) -> AthenaResult:
    """Build an AthenaResult object from execution payloads."""
    state = status["QueryExecution"]["Status"]["State"]
    reason = status["QueryExecution"]["Status"].get("StateChangeReason")
    return AthenaResult(
        query_execution_id=query_execution_id,
        state=state,
        columns=columns,
        rows=rows,
        state_change_reason=reason,
    )


def render_table(columns: list[str], rows: list[dict[str, str | None]], max_width: int = 48) -> str:
    """Render rows as a simple fixed-width text table for terminal output."""
    if not columns:
        return "(no columns)"
    if not rows:
        return "(no rows)"

    def clip(value: str | None) -> str:
        if value is None:
            return "NULL"
        if len(value) <= max_width:
            return value
        return value[: max_width - 3] + "..."

    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(clip(row.get(col))))

    sep = " | "
    header = sep.join(col.ljust(widths[col]) for col in columns)
    rule = "-+-".join("-" * widths[col] for col in columns)
    body = "\n".join(
        sep.join(clip(row.get(col)).ljust(widths[col]) for col in columns)
        for row in rows
    )
    return f"{header}\n{rule}\n{body}"
