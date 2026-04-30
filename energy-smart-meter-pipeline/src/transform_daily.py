# Summary: Build silver and gold daily aggregates for smart meter half-hourly data.
from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql import Window
from pyspark.sql import functions as F

from config import build_parser, load_config
from utils import get_spark, partition_uri


@dataclass
class TransformCounts:
    raw_count: int
    silver_count: int
    peak_count: int
    load_profile_count: int


def build_silver(df: DataFrame) -> DataFrame:
    ts_col = F.to_timestamp("data_collection_log_timestamp")
    return (
        df.withColumn("event_ts", ts_col)
        .withColumn("collection_date", F.to_date("event_ts"))
        .withColumn("hour_of_day", F.hour("event_ts"))
        .withColumn("minute_of_hour", F.minute("event_ts"))
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
    key_cols = ["collection_date", "dno_alias", "secondary_substation_unique_id"]

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


def _duckdb_transform(source_uri: str, run_date: str, silver_out: str, peak_out: str, profile_out: str) -> TransformCounts:
    import duckdb

    con = duckdb.connect(database=":memory:")
    con.execute(
        """
        CREATE TEMP TABLE source_run_date AS
        SELECT *
        FROM read_parquet(?)
        WHERE CAST(data_collection_log_timestamp AS DATE) = CAST(? AS DATE)
        """,
        [source_uri, run_date],
    )

    con.execute(
        """
        CREATE TEMP TABLE silver AS
        SELECT
            *,
            CAST(data_collection_log_timestamp AS DATE) AS collection_date,
            EXTRACT(HOUR FROM data_collection_log_timestamp) AS hour_of_day,
            EXTRACT(MINUTE FROM data_collection_log_timestamp) AS minute_of_hour,
            (EXTRACT(HOUR FROM data_collection_log_timestamp) * 2)
              + CAST(EXTRACT(MINUTE FROM data_collection_log_timestamp) / 30 AS INTEGER) AS half_hour_slot,
            strftime(data_collection_log_timestamp, '%a') AS day_of_week,
            CASE WHEN EXTRACT(DOW FROM data_collection_log_timestamp) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
            secondary_substation_unique_id || '-' || lv_feeder_unique_id AS composite_feeder_id,
            CASE
                WHEN aggregated_device_count_active > 0
                THEN total_consumption_active_import / aggregated_device_count_active
                ELSE NULL
            END AS consumption_per_active_device
        FROM source_run_date
        """
    )

    con.execute(
        """
        COPY (
            SELECT * FROM silver
        ) TO ? (FORMAT PARQUET, OVERWRITE_OR_IGNORE TRUE)
        """,
        [silver_out],
    )

    con.execute(
        """
        CREATE TEMP TABLE gold_peak AS
        WITH ranked AS (
            SELECT
                collection_date,
                dno_alias,
                secondary_substation_unique_id,
                total_consumption_active_import,
                data_collection_log_timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY collection_date, dno_alias, secondary_substation_unique_id
                    ORDER BY total_consumption_active_import DESC, data_collection_log_timestamp ASC
                ) AS rn
            FROM silver
        ),
        agg AS (
            SELECT
                collection_date,
                dno_alias,
                secondary_substation_unique_id,
                SUM(total_consumption_active_import) AS daily_total_consumption,
                AVG(total_consumption_active_import) AS avg_half_hour_consumption,
                AVG(aggregated_device_count_active) AS avg_active_devices,
                COUNT(DISTINCT composite_feeder_id) AS feeder_count,
                COUNT(*) AS reading_count
            FROM silver
            GROUP BY 1,2,3
        )
        SELECT
            agg.collection_date AS consumption_date,
            agg.dno_alias,
            agg.secondary_substation_unique_id,
            ranked.total_consumption_active_import AS peak_consumption,
            ranked.data_collection_log_timestamp AS peak_timestamp,
            agg.daily_total_consumption,
            agg.avg_half_hour_consumption,
            agg.avg_active_devices,
            agg.feeder_count,
            agg.reading_count
        FROM agg
        LEFT JOIN ranked
            ON agg.collection_date = ranked.collection_date
           AND agg.dno_alias = ranked.dno_alias
           AND agg.secondary_substation_unique_id = ranked.secondary_substation_unique_id
           AND ranked.rn = 1
        """
    )

    con.execute(
        """
        COPY (
            SELECT * FROM gold_peak
        ) TO ? (FORMAT PARQUET, OVERWRITE_OR_IGNORE TRUE)
        """,
        [peak_out],
    )

    con.execute(
        """
        CREATE TEMP TABLE gold_profile AS
        SELECT
            collection_date AS consumption_date,
            hour_of_day,
            minute_of_hour,
            half_hour_slot,
            AVG(total_consumption_active_import) AS avg_consumption,
            SUM(total_consumption_active_import) AS total_consumption,
            COUNT(*) AS reading_count,
            COUNT(DISTINCT secondary_substation_unique_id) AS substation_count,
            COUNT(DISTINCT composite_feeder_id) AS feeder_count,
            AVG(consumption_per_active_device) AS avg_consumption_per_active_device
        FROM silver
        GROUP BY 1,2,3,4
        """
    )

    con.execute(
        """
        COPY (
            SELECT * FROM gold_profile
        ) TO ? (FORMAT PARQUET, OVERWRITE_OR_IGNORE TRUE)
        """,
        [profile_out],
    )

    counts = TransformCounts(
        raw_count=con.execute("SELECT COUNT(*) FROM source_run_date").fetchone()[0],
        silver_count=con.execute("SELECT COUNT(*) FROM silver").fetchone()[0],
        peak_count=con.execute("SELECT COUNT(*) FROM gold_peak").fetchone()[0],
        load_profile_count=con.execute("SELECT COUNT(*) FROM gold_profile").fetchone()[0],
    )
    con.close()
    return counts


def run_transform_spark(run_date: str, source_uri: str, silver_out: str, peak_out: str, profile_out: str, region: str) -> TransformCounts:
    spark = get_spark("smart-meter-transform-daily", region)

    # External source dataset is the Bronze layer; filter by run_date at read time.
    filtered = (
        spark.read.parquet(source_uri)
        .withColumn("event_ts", F.to_timestamp("data_collection_log_timestamp"))
        .filter(F.to_date("event_ts") == F.lit(run_date))
        .drop("event_ts")
    )

    silver_df = build_silver(filtered).cache()
    peak_df = build_gold_peak(silver_df)
    profile_df = build_gold_load_profile(silver_df)

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
    parser = build_parser("Transform smart meter half-hourly data into daily silver/gold tables")
    args, _unknown = parser.parse_known_args()
    cfg = load_config(args)
    run_date_str = cfg.run_date.isoformat()

    silver_partition = partition_uri(cfg.silver_output_uri, "collection_date", run_date_str)
    peak_partition = partition_uri(cfg.gold_peak_output_uri, "consumption_date", run_date_str)
    profile_partition = partition_uri(cfg.gold_load_profile_output_uri, "consumption_date", run_date_str)

    if cfg.use_duckdb:
        counts = _duckdb_transform(
            source_uri=cfg.source_uri,
            run_date=run_date_str,
            silver_out=silver_partition,
            peak_out=peak_partition,
            profile_out=profile_partition,
        )
    else:
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
