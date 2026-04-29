# Summary: Validate and profile external Bronze source data for a specific run date without copying it.
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from config import build_parser, load_config
from utils import get_spark


def filter_source_for_date(df: DataFrame, run_date: str) -> DataFrame:
    return (
        df.withColumn("event_ts", F.to_timestamp("data_collection_log_timestamp"))
        .filter(F.to_date("event_ts") == F.lit(run_date))
        .drop("event_ts")
    )


def main() -> None:
    parser = build_parser("Load external Bronze smart meter data for a run date")
    args = parser.parse_args()
    cfg = load_config(args)
    run_date_str = cfg.run_date.isoformat()

    spark = get_spark("smart-meter-load-source", cfg.aws_region)
    source_df = spark.read.parquet(cfg.source_uri)
    filtered = filter_source_for_date(source_df, run_date_str)

    print(
        {
            "source_uri": cfg.source_uri,
            "run_date": run_date_str,
            "row_count": filtered.count(),
            "mode": "read_only_external_bronze",
        }
    )

    spark.stop()


if __name__ == "__main__":
    main()
