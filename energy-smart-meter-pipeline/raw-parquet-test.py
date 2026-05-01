"""Summary: Inspect source parquet metadata and sample rows.

This script prints:
- total row count and row groups
- schema
- min/max timestamp date (derived from row-group statistics)
- sample rows

Download test file:
    aws s3 cp s3://weave.energy/smart-meter.parquet ./smart-meter.parquet --no-sign-request
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pyarrow.parquet as pq


def _to_utc_datetime(value):
    """Convert parquet stats timestamp values to UTC datetime when needed."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, int):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    return value


def get_min_max_collection_date(parquet_file: pq.ParquetFile) -> tuple[datetime | None, datetime | None]:
    """Return global min/max data_collection_log_timestamp from row-group stats."""
    column_name = "data_collection_log_timestamp"
    schema_names = parquet_file.schema.names
    if column_name not in schema_names:
        return None, None

    col_idx = schema_names.index(column_name)
    min_ts = None
    max_ts = None

    for rg_idx in range(parquet_file.num_row_groups):
        col = parquet_file.metadata.row_group(rg_idx).column(col_idx)
        stats = col.statistics
        if not stats or not stats.has_min_max:
            continue

        rg_min = _to_utc_datetime(stats.min)
        rg_max = _to_utc_datetime(stats.max)
        if rg_min is None or rg_max is None:
            continue

        min_ts = rg_min if min_ts is None or rg_min < min_ts else min_ts
        max_ts = rg_max if max_ts is None or rg_max > max_ts else max_ts

    return min_ts, max_ts


pf = pq.ParquetFile("smart-meter.parquet")
print("num_rows:", pf.metadata.num_rows)
print("num_row_groups:", pf.num_row_groups)
print("schema:")
print(pf.schema)

min_ts, max_ts = get_min_max_collection_date(pf)
if min_ts and max_ts:
    print("min_data_collection_date_utc:", min_ts.date().isoformat())
    print("max_data_collection_date_utc:", max_ts.date().isoformat())
    print("min_data_collection_timestamp_utc:", min_ts.isoformat())
    print("max_data_collection_timestamp_utc:", max_ts.isoformat())
else:
    print("min/max timestamp unavailable from parquet statistics")

df = pd.read_parquet("smart-meter.parquet").head(10)
print(df)
