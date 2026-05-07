# Summary: Build silver and gold daily aggregates for smart meter half-hourly data.
"""Daily transformation pipeline for smart meter data.

This module transforms external Bronze input into:
- Silver cleaned half-hourly dataset,
- Gold peak-demand table by substation/day,
- Gold average load profile table by half-hour slot/day.

It supports:
- AWS Glue/Spark execution (production path),
- local Spark execution for development and testing.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql import Window
from pyspark.sql import functions as F

from config import build_parser, load_config
from utils import get_spark, partition_uri


@dataclass
class TransformCounts:
    """Simple row-count metrics emitted after transformation."""

    raw_count: int
    silver_count: int
    peak_count: int
    load_profile_count: int


def build_silver(df: DataFrame) -> DataFrame:
    """Construct silver table by deriving time and feeder-level fields."""
    ts_col = F.to_timestamp("data_collection_log_timestamp")
    return (
        # Normalize consumption type so Athena schema can stay consistent as DOUBLE.
        df.withColumn("total_consumption_active_import", F.col("total_consumption_active_import").cast("double"))
        .withColumn("event_ts", ts_col)
        .withColumn("collection_date", F.to_date("event_ts"))
        .withColumn("hour_of_day", F.hour("event_ts"))
        .withColumn("minute_of_hour", F.minute("event_ts"))
        # Convert HH:MM into a zero-based half-hour slot index (0..47).
        .withColumn("half_hour_slot", (F.col("hour_of_day") * F.lit(2)) + (F.col("minute_of_hour") / 30).cast("int"))
        .withColumn("day_of_week", F.date_format("event_ts", "E"))
        .withColumn("is_weekend", F.dayofweek("event_ts").isin(1, 7))
        .withColumn(
            "composite_feeder_id",
            F.concat_ws("-", F.col("secondary_substation_unique_id"), F.col("lv_feeder_unique_id")),
        )
        .withColumn(
            "consumption_per_active_device",
            F.when(
                F.col("aggregated_device_count_active") > 0,
                F.col("total_consumption_active_import") / F.col("aggregated_device_count_active"),
            ).otherwise(F.lit(None)),
        )
        .drop("event_ts")
    )


def build_gold_peak(silver_df: DataFrame) -> DataFrame:
    """Aggregate daily peak and summary stats per substation."""
    key_cols = ["collection_date", "dno_alias", "secondary_substation_unique_id"]

    # Rank rows so rank=1 is the peak timestamp for each grouping key.
    ranked = silver_df.withColumn(
        "peak_rank",
        F.row_number().over(
            Window.partitionBy(*key_cols).orderBy(
                F.col("total_consumption_active_import").desc(),
                F.col("data_collection_log_timestamp").asc(),
            )
        ),
    )

    peak_rows = ranked.filter(F.col("peak_rank") == 1).select(
        "collection_date",
        "dno_alias",
        "secondary_substation_unique_id",
        F.col("total_consumption_active_import").alias("peak_consumption"),
        F.col("data_collection_log_timestamp").alias("peak_timestamp"),
    )

    daily_stats = silver_df.groupBy(*key_cols).agg(
        F.sum("total_consumption_active_import").alias("daily_total_consumption"),
        F.avg("total_consumption_active_import").alias("avg_half_hour_consumption"),
        F.avg("aggregated_device_count_active").alias("avg_active_devices"),
        F.countDistinct("composite_feeder_id").alias("feeder_count"),
        F.count(F.lit(1)).alias("reading_count"),
    )

    return (
        daily_stats.join(peak_rows, on=key_cols, how="left")
        .withColumnRenamed("collection_date", "consumption_date")
        .select(
            "consumption_date",
            "dno_alias",
            "secondary_substation_unique_id",
            "peak_consumption",
            "peak_timestamp",
            "daily_total_consumption",
            "avg_half_hour_consumption",
            "avg_active_devices",
            "feeder_count",
            "reading_count",
        )
    )


def build_gold_load_profile(silver_df: DataFrame) -> DataFrame:
    """Aggregate average demand shape by half-hour slot for each day."""
    return (
        silver_df.groupBy("collection_date", "hour_of_day", "minute_of_hour", "half_hour_slot")
        .agg(
            F.avg("total_consumption_active_import").alias("avg_consumption"),
            F.sum("total_consumption_active_import").alias("total_consumption"),
            F.count(F.lit(1)).alias("reading_count"),
            F.countDistinct("secondary_substation_unique_id").alias("substation_count"),
            F.countDistinct("composite_feeder_id").alias("feeder_count"),
            F.avg("consumption_per_active_device").alias("avg_consumption_per_active_device"),
        )
        .withColumnRenamed("collection_date", "consumption_date")
        .select(
            "consumption_date",
            "hour_of_day",
            "minute_of_hour",
            "half_hour_slot",
            "avg_consumption",
            "total_consumption",
            "reading_count",
            "substation_count",
            "feeder_count",
            "avg_consumption_per_active_device",
        )
    )


def run_transform_spark(run_date: str, source_uri: str, silver_out: str, peak_out: str, profile_out: str, region: str) -> TransformCounts:
    """Run production Spark/Glue transformation path."""
    spark = get_spark("smart-meter-transform-daily", region)

    # External source dataset is the Bronze layer; filter by run_date at read time.
    filtered = (
        spark.read.parquet(source_uri)
        .withColumn("event_ts", F.to_timestamp("data_collection_log_timestamp"))
        .filter(F.to_date("event_ts") == F.lit(run_date))
        .drop("event_ts")
    )

    # Build silver then both gold outputs from the same filtered dataset.
    silver_df = build_silver(filtered).cache()
    peak_df = build_gold_peak(silver_df)
    profile_df = build_gold_load_profile(silver_df)

    # Idempotent per-date writes via partition-specific output paths.
    silver_df.write.mode("overwrite").format("parquet").save(silver_out)
    peak_df.write.mode("overwrite").format("parquet").save(peak_out)
    profile_df.write.mode("overwrite").format("parquet").save(profile_out)

    counts = TransformCounts(
        raw_count=filtered.count(),
        silver_count=silver_df.count(),
        peak_count=peak_df.count(),
        load_profile_count=profile_df.count(),
    )

    spark.stop()
    return counts


def main() -> None:
    """CLI entrypoint used by Glue job and local development runs."""
    parser = build_parser("Transform smart meter half-hourly data into daily silver/gold tables")

    # parse_known_args lets Glue pass extra reserved arguments without failing.
    args, _unknown = parser.parse_known_args()
    cfg = load_config(args)
    run_date_str = cfg.run_date.isoformat()

    silver_partition = partition_uri(cfg.silver_output_uri, "collection_date", run_date_str)
    peak_partition = partition_uri(cfg.gold_peak_output_uri, "consumption_date", run_date_str)
    profile_partition = partition_uri(cfg.gold_load_profile_output_uri, "consumption_date", run_date_str)

    counts = run_transform_spark(
        run_date=run_date_str,
        source_uri=cfg.source_uri,
        silver_out=silver_partition,
        peak_out=peak_partition,
        profile_out=profile_partition,
        region=cfg.aws_region,
    )

    print(
        {
            "run_date": run_date_str,
            "source_uri": cfg.source_uri,
            "raw_count": counts.raw_count,
            "silver_count": counts.silver_count,
            "peak_count": counts.peak_count,
            "load_profile_count": counts.load_profile_count,
        }
    )


if __name__ == "__main__":
    main()
