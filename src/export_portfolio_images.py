# Summary: Query Athena gold tables and export portfolio charts as static PNG images under docs/images.
"""Generate portfolio-ready smart-meter charts from Athena.

This script runs curated SQL queries against gold tables and writes image files that can
be embedded directly in GitHub README pages without needing a BI tool or web app.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import boto3
import matplotlib.pyplot as plt
import pandas as pd

from athena_utils import fetch_rows, run_query
from config import load_config


def _rows_to_df(rows: list[dict[str, str | None]]) -> pd.DataFrame:
    """Convert Athena row dicts into a pandas DataFrame."""
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Cast listed columns to numeric in-place when present."""
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _run_sql(
    athena,
    *,
    sql: str,
    database: str,
    output_location: str,
    workgroup: str,
    max_rows: int = 10000,
) -> pd.DataFrame:
    """Run Athena SQL and return a pandas DataFrame."""
    qid, status = run_query(
        athena,
        query=sql,
        database=database,
        output_location=output_location,
        workgroup=workgroup,
    )

    state = status["QueryExecution"]["Status"]["State"]
    if state != "SUCCEEDED":
        reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
        raise RuntimeError(f"Query failed ({qid}) with state={state}: {reason}")

    _cols, rows = fetch_rows(athena, query_execution_id=qid, max_rows=max_rows)
    return _rows_to_df(rows)


def _save(fig: plt.Figure, path: Path) -> None:
    """Save a matplotlib figure with consistent export settings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _chart_dno_share(df: pd.DataFrame, out_dir: Path) -> Path:
    """Create DNO share bar chart."""
    df = _num(df, ["share_of_total", "total_consumption"]).sort_values("share_of_total", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(df["dno_alias"], df["share_of_total"] * 100)
    ax.set_title("Share of Total Demand by DNO")
    ax.set_ylabel("Share of Total (%)")
    ax.set_xlabel("DNO")
    ax.grid(axis="y", alpha=0.3)
    out_path = out_dir / "dno_share_of_total.png"
    _save(fig, out_path)
    return out_path


def _chart_load_shape(df: pd.DataFrame, out_dir: Path) -> Path:
    """Create half-hour load shape line chart."""
    df = _num(df, ["half_hour_slot", "mean_slot_consumption"]).sort_values("half_hour_slot")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(df["half_hour_slot"], df["mean_slot_consumption"], linewidth=2)
    ax.set_title("Average Daily Load Shape (Half-Hour Slots)")
    ax.set_xlabel("Half-hour Slot (0-47)")
    ax.set_ylabel("Mean Consumption")
    ax.grid(alpha=0.3)
    out_path = out_dir / "avg_daily_load_shape.png"
    _save(fig, out_path)
    return out_path


def _chart_peak_hour_distribution(df: pd.DataFrame, out_dir: Path) -> Path:
    """Create histogram-style bar chart of peak hours."""
    df = _num(df, ["peak_hour", "substation_days"]).sort_values("peak_hour")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(df["peak_hour"], df["substation_days"], width=0.8)
    ax.set_title("Distribution of Substation Peak Hours")
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Substation-Day Count")
    ax.set_xticks(range(0, 24, 1))
    ax.grid(axis="y", alpha=0.3)
    out_path = out_dir / "peak_hour_distribution.png"
    _save(fig, out_path)
    return out_path


def _chart_concentration(df: pd.DataFrame, out_dir: Path) -> Path:
    """Create top-N concentration chart with cumulative share line."""
    df = _num(df, ["rn", "share_of_total", "total_consumption"]).sort_values("rn")
    top = df[df["rn"] <= 10].copy()
    top["cum_share"] = top["share_of_total"].cumsum() * 100

    fig, ax1 = plt.subplots(figsize=(10, 5.2))
    ax1.bar(top["rn"].astype(int).astype(str), top["share_of_total"] * 100, color="#4e79a7")
    ax1.set_xlabel("Substation Rank")
    ax1.set_ylabel("Individual Share (%)", color="#4e79a7")
    ax1.tick_params(axis="y", labelcolor="#4e79a7")
    ax1.set_title("Demand Concentration in Top 10 Substations")
    ax1.grid(axis="y", alpha=0.2)

    ax2 = ax1.twinx()
    ax2.plot(top["rn"].astype(int).astype(str), top["cum_share"], color="#e15759", marker="o")
    ax2.set_ylabel("Cumulative Share (%)", color="#e15759")
    ax2.tick_params(axis="y", labelcolor="#e15759")

    out_path = out_dir / "top10_concentration.png"
    _save(fig, out_path)
    return out_path


def _chart_weekday_weekend(df: pd.DataFrame, out_dir: Path) -> Path:
    """Create grouped bar chart for weekday/weekend evening vs night ratio."""
    df = _num(df, ["evening_to_night_ratio", "evening_avg", "night_avg"])
    fig, ax = plt.subplots(figsize=(7, 4.8))
    ax.bar(df["day_type"], df["evening_to_night_ratio"], color=["#59a14f", "#f28e2b"])
    ax.axhline(1.0, linestyle="--", linewidth=1, color="gray")
    ax.set_title("Evening-to-Night Demand Ratio: Weekday vs Weekend")
    ax.set_ylabel("Evening/Night Ratio")
    ax.set_xlabel("Day Type")
    ax.grid(axis="y", alpha=0.3)
    out_path = out_dir / "weekday_weekend_evening_ratio.png"
    _save(fig, out_path)
    return out_path


def main() -> None:
    """CLI entrypoint for generating portfolio chart images."""
    parser = argparse.ArgumentParser(description="Export portfolio chart images from Athena gold tables")
    parser.add_argument("--database", default=None, help="Athena database (defaults to config)")
    parser.add_argument("--workgroup", default="energy-smart-meter-pipeline-dev-athena", help="Athena workgroup")
    parser.add_argument("--output-s3-uri", default=None, help="Athena query output S3 URI")
    parser.add_argument("--aws-region", default=None, help="AWS region")
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "images"),
        help="Directory for PNG chart exports",
    )
    args = parser.parse_args()

    cfg = load_config(args)
    database = args.database or cfg.glue_database
    output_s3_uri = args.output_s3_uri or cfg.athena_output_s3_uri

    if "replace-me-" in output_s3_uri:
        raise SystemExit("Provide --output-s3-uri or set ATHENA_OUTPUT_S3_URI to a real S3 location.")

    athena = boto3.client("athena", region_name=cfg.aws_region)
    out_dir = Path(args.out_dir)

    dno_share_sql = """
    SELECT
      dno_alias,
      SUM(daily_total_consumption) AS total_consumption,
      SUM(daily_total_consumption) / SUM(SUM(daily_total_consumption)) OVER () AS share_of_total
    FROM energy_smart_meter.gold_peak_demand_substation_day
    GROUP BY 1
    ORDER BY total_consumption DESC
    """
    load_shape_sql = """
    SELECT
      half_hour_slot,
      AVG(avg_consumption) AS mean_slot_consumption
    FROM energy_smart_meter.gold_avg_load_profile_day
    GROUP BY 1
    ORDER BY 1
    """
    peak_hour_sql = """
    SELECT
      hour(peak_timestamp) AS peak_hour,
      COUNT(*) AS substation_days
    FROM energy_smart_meter.gold_peak_demand_substation_day
    GROUP BY 1
    ORDER BY 1
    """
    concentration_sql = """
    WITH substation_totals AS (
      SELECT
        secondary_substation_unique_id,
        SUM(daily_total_consumption) AS total_consumption
      FROM energy_smart_meter.gold_peak_demand_substation_day
      GROUP BY 1
    ), ranked AS (
      SELECT
        ROW_NUMBER() OVER (ORDER BY total_consumption DESC) AS rn,
        total_consumption,
        total_consumption / SUM(total_consumption) OVER () AS share_of_total
      FROM substation_totals
    )
    SELECT rn, total_consumption, share_of_total
    FROM ranked
    WHERE rn <= 20
    ORDER BY rn
    """
    weekday_weekend_sql = """
    WITH labeled AS (
      SELECT
        CASE WHEN day_of_week(consumption_date) IN (6, 7) THEN 'weekend' ELSE 'weekday' END AS day_type,
        half_hour_slot,
        avg_consumption
      FROM energy_smart_meter.gold_avg_load_profile_day
    ), agg AS (
      SELECT
        day_type,
        AVG(CASE WHEN half_hour_slot BETWEEN 34 AND 41 THEN avg_consumption END) AS evening_avg,
        AVG(CASE WHEN half_hour_slot BETWEEN 4 AND 11 THEN avg_consumption END) AS night_avg
      FROM labeled
      GROUP BY 1
    )
    SELECT
      day_type,
      evening_avg,
      night_avg,
      evening_avg / NULLIF(night_avg, 0) AS evening_to_night_ratio
    FROM agg
    ORDER BY day_type
    """

    exported: list[Path] = []
    exported.append(_chart_dno_share(_run_sql(athena, sql=dno_share_sql, database=database, output_location=output_s3_uri, workgroup=args.workgroup), out_dir))
    exported.append(_chart_load_shape(_run_sql(athena, sql=load_shape_sql, database=database, output_location=output_s3_uri, workgroup=args.workgroup), out_dir))
    exported.append(_chart_peak_hour_distribution(_run_sql(athena, sql=peak_hour_sql, database=database, output_location=output_s3_uri, workgroup=args.workgroup), out_dir))
    exported.append(_chart_concentration(_run_sql(athena, sql=concentration_sql, database=database, output_location=output_s3_uri, workgroup=args.workgroup), out_dir))
    exported.append(_chart_weekday_weekend(_run_sql(athena, sql=weekday_weekend_sql, database=database, output_location=output_s3_uri, workgroup=args.workgroup), out_dir))

    print("Exported chart images:")
    for p in exported:
        print(f"- {p}")


if __name__ == "__main__":
    main()
