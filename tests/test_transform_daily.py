# Summary: Unit tests for daily transformation logic and aggregate correctness.
"""Tests for transformation logic.

The test builds a tiny in-memory Spark dataset and verifies:
- silver row count,
- gold peak aggregation correctness,
- gold load-profile slot aggregation correctness.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pyspark.errors import PySparkRuntimeError
from pyspark.sql import SparkSession

from transform_daily import apply_zscore_quality_flag, build_gold_load_profile, build_gold_peak, build_silver


def _get_local_spark(app_name: str) -> SparkSession:
    """Create a local Spark session or skip tests when Java is unavailable."""
    try:
        return SparkSession.builder.master("local[1]").appName(app_name).getOrCreate()
    except PySparkRuntimeError as exc:
        # Local Spark requires Java; skip gracefully in environments without it.
        if "JAVA_GATEWAY_EXITED" in str(exc):
            pytest.skip("Java runtime is required for local Spark tests")
        raise


def test_transform_builds_expected_aggregates() -> None:
    """Validate key aggregate outputs on a small deterministic dataset."""
    spark = _get_local_spark("test-transform-daily")

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

    # Execute the same transformation functions used in the production pipeline.
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


def test_zscore_flag_marks_outlier_as_clip() -> None:
    """Validate hybrid policy clips extreme z-score rows instead of dropping them."""
    spark = _get_local_spark("test-zscore-flag")

    current = spark.createDataFrame(
        [
            {
                "dataset_id": "d-current",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 500.0,
                "data_collection_log_timestamp": datetime(2024, 2, 12, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            }
        ]
    )
    history = spark.createDataFrame(
        [
            {
                "dataset_id": "d-h1",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 100.0,
                "data_collection_log_timestamp": datetime(2024, 2, 11, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            },
            {
                "dataset_id": "d-h2",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 110.0,
                "data_collection_log_timestamp": datetime(2024, 2, 10, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            },
            {
                "dataset_id": "d-h3",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 90.0,
                "data_collection_log_timestamp": datetime(2024, 2, 9, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            },
        ]
    )

    flagged = apply_zscore_quality_flag(
        build_silver(current),
        build_silver(history),
        threshold=3.0,
        min_history_rows=3,
    )
    row = flagged.collect()[0]

    assert row.dq_action == "CLIP"
    assert row.data_quality_flag == "PASS"
    assert row.dq_reason == "ZSCORE_CLIPPED"
    assert row.consumption_zscore is not None
    assert row.consumption_zscore > 3.0
    assert row.adjusted_total_consumption_active_import is not None
    assert row.adjusted_total_consumption_active_import < row.total_consumption_active_import

    spark.stop()


def test_zscore_flag_marks_normal_reading_as_pass() -> None:
    """Ensure an in-range reading is not flagged when enough baseline history exists."""
    spark = _get_local_spark("test-zscore-pass")

    current = spark.createDataFrame(
        [
            {
                "dataset_id": "d-current",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 105.0,
                "data_collection_log_timestamp": datetime(2024, 2, 12, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            }
        ]
    )
    history = spark.createDataFrame(
        [
            {
                "dataset_id": "d-h1",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 100.0,
                "data_collection_log_timestamp": datetime(2024, 2, 11, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            },
            {
                "dataset_id": "d-h2",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 110.0,
                "data_collection_log_timestamp": datetime(2024, 2, 10, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            },
            {
                "dataset_id": "d-h3",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 90.0,
                "data_collection_log_timestamp": datetime(2024, 2, 9, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            },
        ]
    )

    flagged = apply_zscore_quality_flag(
        build_silver(current),
        build_silver(history),
        threshold=6.0,
        min_history_rows=3,
    )
    row = flagged.collect()[0]

    assert row.data_quality_flag == "PASS"
    assert row.dq_reason is None
    assert row.dq_action == "KEEP"
    assert row.consumption_zscore is not None
    assert row.consumption_zscore < 6.0
    assert row.adjusted_total_consumption_active_import == row.total_consumption_active_import

    spark.stop()


def test_zscore_flag_uses_min_history_threshold() -> None:
    """Verify rows remain PASS with null z-score when history is below minimum threshold."""
    spark = _get_local_spark("test-zscore-min-history")

    current = spark.createDataFrame(
        [
            {
                "dataset_id": "d-current",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 9999.0,
                "data_collection_log_timestamp": datetime(2024, 2, 12, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            }
        ]
    )
    # Only two history rows; min_history_rows is set to three.
    history = spark.createDataFrame(
        [
            {
                "dataset_id": "d-h1",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 100.0,
                "data_collection_log_timestamp": datetime(2024, 2, 11, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            },
            {
                "dataset_id": "d-h2",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 110.0,
                "data_collection_log_timestamp": datetime(2024, 2, 10, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            },
        ]
    )

    flagged = apply_zscore_quality_flag(
        build_silver(current),
        build_silver(history),
        threshold=3.0,
        min_history_rows=3,
    )
    row = flagged.collect()[0]

    assert row.zscore_history_count == 2
    assert row.consumption_zscore is None
    assert row.data_quality_flag == "PASS"
    assert row.dq_action == "KEEP"
    assert row.dq_reason is None

    spark.stop()


def test_gold_aggregations_exclude_failed_rows() -> None:
    """Confirm Gold aggregates are calculated only from rows flagged as PASS."""
    spark = _get_local_spark("test-gold-excludes-fail")

    rows = [
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
            "data_quality_flag": "PASS",
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
            "data_quality_flag": "FAIL",
        },
    ]

    silver_with_flag = build_silver(spark.createDataFrame(rows))
    gold_input_df = silver_with_flag.filter("data_quality_flag = 'PASS'")

    peak_df = build_gold_peak(gold_input_df)
    profile_df = build_gold_load_profile(gold_input_df)

    peak_row = peak_df.collect()[0]
    slot_row = profile_df.collect()[0]

    # Only the PASS row should contribute to Gold metrics.
    assert peak_row.peak_consumption == 100.0
    assert peak_row.daily_total_consumption == 100.0
    assert slot_row.total_consumption == 100.0
    assert slot_row.reading_count == 1

    spark.stop()


def test_invalid_row_is_marked_drop() -> None:
    """Ensure hard-invalid rows are marked DROP regardless of z-score math."""
    spark = _get_local_spark("test-invalid-drop")

    current = spark.createDataFrame(
        [
            {
                "dataset_id": "d-current",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 0,
                "total_consumption_active_import": -1.0,
                "data_collection_log_timestamp": None,
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            }
        ]
    )
    baseline = spark.createDataFrame(
        [
            {
                "dataset_id": "d-h1",
                "dno_alias": "DNO_A",
                "aggregated_device_count_active": 10,
                "total_consumption_active_import": 100.0,
                "data_collection_log_timestamp": datetime(2024, 2, 11, 0, 0, 0),
                "geometry": "POINT(0 0)",
                "secondary_substation_unique_id": "SS1",
                "lv_feeder_unique_id": "F1",
                "bbox": "",
            }
        ]
    )

    flagged = apply_zscore_quality_flag(
        build_silver(current),
        build_silver(baseline),
        threshold=3.0,
        min_history_rows=1,
    )
    row = flagged.collect()[0]

    assert row.dq_action == "DROP"
    assert row.data_quality_flag == "FAIL"
    assert row.dq_reason == "INVALID_RULE"

    spark.stop()
