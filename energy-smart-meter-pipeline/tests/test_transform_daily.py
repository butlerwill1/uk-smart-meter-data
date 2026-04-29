# Summary: Unit tests for daily transformation logic and aggregate correctness.
from __future__ import annotations

from datetime import datetime

import pytest
from pyspark.errors import PySparkRuntimeError
from pyspark.sql import SparkSession

from transform_daily import build_gold_load_profile, build_gold_peak, build_silver


def test_transform_builds_expected_aggregates() -> None:
    try:
        spark = SparkSession.builder.master("local[1]").appName("test-transform-daily").getOrCreate()
    except PySparkRuntimeError as exc:
        if "JAVA_GATEWAY_EXITED" in str(exc):
            pytest.skip("Java runtime is required for local Spark tests")
        raise

    data = [
        {
            "dataset_id": "d1",
            "dno_alias": "DNO_A",
            "aggregated_device_count_active": 10,
            "total_consumption_active_import": 100.0,
            "data_collection_log_timestamp": datetime(2024, 2, 12, 0, 0, 0),
            "geometry": "POINT(0 0)",
            "secondary_substation_unique_id": "SS1",
            "lv_feeder_unique_id": "F1",
            "bbox": "",
            "collection_date": datetime(2024, 2, 12).date(),
        },
        {
            "dataset_id": "d1",
            "dno_alias": "DNO_A",
            "aggregated_device_count_active": 10,
            "total_consumption_active_import": 150.0,
            "data_collection_log_timestamp": datetime(2024, 2, 12, 0, 30, 0),
            "geometry": "POINT(0 0)",
            "secondary_substation_unique_id": "SS1",
            "lv_feeder_unique_id": "F1",
            "bbox": "",
            "collection_date": datetime(2024, 2, 12).date(),
        },
        {
            "dataset_id": "d1",
            "dno_alias": "DNO_A",
            "aggregated_device_count_active": 20,
            "total_consumption_active_import": 200.0,
            "data_collection_log_timestamp": datetime(2024, 2, 12, 0, 0, 0),
            "geometry": "POINT(0 0)",
            "secondary_substation_unique_id": "SS2",
            "lv_feeder_unique_id": "F2",
            "bbox": "",
            "collection_date": datetime(2024, 2, 12).date(),
        },
    ]

    raw_df = spark.createDataFrame(data)
    silver_df = build_silver(raw_df)
    peak_df = build_gold_peak(silver_df)
    profile_df = build_gold_load_profile(silver_df)

    assert silver_df.count() == 3
    assert peak_df.count() == 2
    assert profile_df.count() == 2

    peak_ss1 = peak_df.filter("secondary_substation_unique_id = 'SS1'").collect()[0]
    assert peak_ss1.peak_consumption == 150.0
    assert peak_ss1.daily_total_consumption == 250.0

    slot_zero = profile_df.filter("half_hour_slot = 0").collect()[0]
    assert slot_zero.reading_count == 2

    spark.stop()
