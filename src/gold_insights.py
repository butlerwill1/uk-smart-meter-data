# Summary: Run curated gold-table Athena insight queries and print portfolio-ready findings.
"""Portfolio insights runner for gold smart-meter tables.

This script executes SQL files in `sql/insights/` and synthesizes key findings.
Use it after your Silver/Gold tables are populated.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import boto3

from athena_utils import fetch_rows, run_query
from config import load_config


INSIGHT_SQL_FILES = [
    "02_top_substations_by_total.sql",
    "03_system_peak_day.sql",
    "04_avg_load_shape_peak_trough.sql",
    "05_weekday_weekend_profile.sql",
    "06_substation_concentration.sql",
    "07_peak_window_concentration.sql",
    "08_day_total_volatility.sql",
    "09_evening_ramp_weekday_vs_weekend.sql",
    "10_dno_outlier_screen.sql",
]


def _run_sql_file(athena, *, sql_path: Path, database: str, output_location: str, workgroup: str, max_rows: int = 500):
    """Run one SQL file and return rows as dictionaries."""
    query = sql_path.read_text(encoding="utf-8")
    qid, status = run_query(
        athena,
        query=query,
        database=database,
        output_location=output_location,
        workgroup=workgroup,
    )

    state = status["QueryExecution"]["Status"]["State"]
    if state != "SUCCEEDED":
        reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
        raise RuntimeError(f"{sql_path.name} failed with state={state}: {reason}")

    _columns, rows = fetch_rows(athena, query_execution_id=qid, max_rows=max_rows)
    return rows


def _safe_float(value: str | None) -> float:
    """Parse optional string to float with null-safe fallback."""
    if value is None or value == "":
        return 0.0
    return float(value)


def _slot_to_hhmm(slot: int) -> str:
    """Convert a half-hour slot index into HH:MM string."""
    hour = slot // 2
    minute = 30 if slot % 2 else 0
    return f"{hour:02d}:{minute:02d}"


def _analyze(rows_by_file: dict[str, list[dict[str, str | None]]]) -> list[str]:
    """Build human-readable insight bullets from query outputs."""
    insights: list[str] = []

    top_substations = rows_by_file["02_top_substations_by_total.sql"]
    if top_substations:
        top = top_substations[0]
        insights.append(
            "Top substation by mean daily consumption: "
            f"{top['secondary_substation_unique_id']} ({top['dno_alias']}), "
            f"avg daily total={_safe_float(top['avg_daily_total_consumption']):,.2f}, "
            f"max observed peak={_safe_float(top['max_observed_peak']):,.2f}."
        )

    peak_days = rows_by_file["03_system_peak_day.sql"]
    if peak_days:
        peak = peak_days[0]
        insights.append(
            "Highest system-demand day: "
            f"{peak['consumption_date']} ({peak['dno_alias']}), "
            f"system daily total={_safe_float(peak['system_daily_total']):,.2f}, "
            f"active substations={peak['active_substations']}."
        )

    load_shape = rows_by_file["04_avg_load_shape_peak_trough.sql"]
    if load_shape:
        peak_slot = load_shape[0]
        trough_slot = load_shape[-1]
        peak_slot_idx = int(float(peak_slot["half_hour_slot"]))
        trough_slot_idx = int(float(trough_slot["half_hour_slot"]))
        insights.append(
            "Load-shape peak/trough: "
            f"highest average slot={_slot_to_hhmm(peak_slot_idx)} "
            f"({_safe_float(peak_slot['mean_slot_consumption']):,.2f}), "
            f"lowest average slot={_slot_to_hhmm(trough_slot_idx)} "
            f"({_safe_float(trough_slot['mean_slot_consumption']):,.2f})."
        )

    weekday_weekend = rows_by_file["05_weekday_weekend_profile.sql"]
    weekday_avg = [
        _safe_float(r["mean_avg_consumption"]) for r in weekday_weekend if r.get("day_type") == "weekday"
    ]
    weekend_avg = [
        _safe_float(r["mean_avg_consumption"]) for r in weekday_weekend if r.get("day_type") == "weekend"
    ]
    if weekday_avg and weekend_avg:
        weekday_mean = sum(weekday_avg) / len(weekday_avg)
        weekend_mean = sum(weekend_avg) / len(weekend_avg)
        delta_pct = ((weekend_mean - weekday_mean) / weekday_mean * 100.0) if weekday_mean else 0.0
        insights.append(
            "Weekday vs weekend baseline: "
            f"weekday mean slot demand={weekday_mean:,.2f}, "
            f"weekend mean slot demand={weekend_mean:,.2f} ({delta_pct:+.2f}%)."
        )

    concentration = rows_by_file["06_substation_concentration.sql"]
    if concentration:
        top_5_share = sum(_safe_float(r["share_of_total"]) for r in concentration[:5]) * 100.0
        top_10_share = sum(_safe_float(r["share_of_total"]) for r in concentration[:10]) * 100.0
        insights.append(
            "Demand concentration: "
            f"top 5 substations contribute {top_5_share:.2f}% of total demand; "
            f"top 10 contribute {top_10_share:.2f}%."
        )

    peak_window = rows_by_file["07_peak_window_concentration.sql"]
    if peak_window:
        row = peak_window[0]
        insights.append(
            "Temporal concentration of peaks: "
            f"{_safe_float(row['evening_peak_share']) * 100.0:.2f}% of substation-day peaks occur between 17:00 and 20:59, "
            f"vs {_safe_float(row['overnight_peak_share']) * 100.0:.2f}% between 00:00 and 05:59."
        )

    volatility = rows_by_file["08_day_total_volatility.sql"]
    if volatility:
        row = volatility[0]
        insights.append(
            "System volatility: "
            f"coefficient of variation for daily total demand is {_safe_float(row['cv_day_total']):.3f} "
            f"({_safe_float(row['stddev_day_total']):,.2f} stddev over {_safe_float(row['mean_day_total']):,.2f} mean)."
        )

    ramp = rows_by_file["09_evening_ramp_weekday_vs_weekend.sql"]
    weekday_row = next((r for r in ramp if r.get("day_type") == "weekday"), None)
    weekend_row = next((r for r in ramp if r.get("day_type") == "weekend"), None)
    if weekday_row and weekend_row:
        insights.append(
            "Weekday/weekend ramp signature: "
            f"weekday evening-to-night ratio={_safe_float(weekday_row['evening_to_night_ratio']):.3f}, "
            f"weekend ratio={_safe_float(weekend_row['evening_to_night_ratio']):.3f}."
        )

    outlier_screen = rows_by_file["10_dno_outlier_screen.sql"]
    if outlier_screen:
        dominant = outlier_screen[0]
        ratio = _safe_float(dominant["mean_to_median_ratio"])
        if ratio > 10:
            insights.append(
                "Distribution alert: "
                f"{dominant['dno_alias']} shows strong right-tail skew (mean/median={ratio:,.2f}), "
                "suggesting a small number of very high-consumption substations dominate totals."
            )

    return insights


def main() -> None:
    """CLI entrypoint to compute and print insight bullets from gold tables."""
    parser = argparse.ArgumentParser(description="Generate insights from Athena gold smart-meter tables")
    parser.add_argument("--database", default=None, help="Athena database (defaults to config)")
    parser.add_argument("--workgroup", default="energy-smart-meter-pipeline-dev-athena", help="Athena workgroup")
    parser.add_argument("--output-s3-uri", default=None, help="Athena output S3 URI")
    parser.add_argument("--aws-region", default=None, help="AWS region")
    parser.add_argument(
        "--insights-dir",
        default=str(Path(__file__).resolve().parents[1] / "sql" / "insights"),
        help="Directory containing insight SQL files",
    )
    args = parser.parse_args()

    cfg = load_config(args)
    database = args.database or cfg.glue_database
    output_s3_uri = args.output_s3_uri or cfg.athena_output_s3_uri

    if "replace-me-" in output_s3_uri:
        raise SystemExit("Provide --output-s3-uri or set ATHENA_OUTPUT_S3_URI to a real S3 location.")

    athena = boto3.client("athena", region_name=cfg.aws_region)
    insights_dir = Path(args.insights_dir)

    rows_by_file: dict[str, list[dict[str, str | None]]] = {}
    for file_name in INSIGHT_SQL_FILES:
        sql_path = insights_dir / file_name
        rows_by_file[file_name] = _run_sql_file(
            athena,
            sql_path=sql_path,
            database=database,
            output_location=output_s3_uri,
            workgroup=args.workgroup,
        )

    insights = _analyze(rows_by_file)

    print("Portfolio Insights")
    print("------------------")
    for item in insights:
        print(f"- {item}")


if __name__ == "__main__":
    main()
