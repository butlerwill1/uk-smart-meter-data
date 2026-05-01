# Summary: Inspect silver parquet file shape, sample rows, and date ranges.
"""Quick local inspection for silver parquet output.

This script prints:
- total row count and row groups
- schema
- sample rows
- min/max collection date
- min/max timestamp (if present)

Download test file:
    aws s3 ls s3://weave-smart-meter-data/portfolio/energy/silver/smart_meter_half_hourly_clean/collection_date=2024-09-01/ --region eu-west-2
    aws s3 cp s3://weave-smart-meter-data/portfolio/energy/silver/smart_meter_half_hourly_clean/collection_date=2024-09-01/<part-file>.snappy.parquet ./silver.parquet --region eu-west-2

Note:
    Pick a data file that starts with "part-" and ends with ".parquet", not "_SUCCESS".
"""

from __future__ import annotations

import pandas as pd
import pyarrow.parquet as pq


PARQUET_PATH = "silver-2024-02-02.parquet"


pf = pq.ParquetFile(PARQUET_PATH)
print("rows:", pf.metadata.num_rows)
print("row_groups:", pf.num_row_groups)
print("schema:")
print(pf.schema)

# Load into pandas for easy row preview and min/max date checks.
df = pd.read_parquet(PARQUET_PATH)
print("\nSample rows (first 10):")
print(df.head(10))

if "collection_date" in df.columns and len(df) > 0:
    print("\ncollection_date min:", pd.to_datetime(df["collection_date"]).min())
    print("collection_date max:", pd.to_datetime(df["collection_date"]).max())
else:
    print("\ncollection_date column not found or file has no rows")

if "data_collection_log_timestamp" in df.columns and len(df) > 0:
    ts = pd.to_datetime(df["data_collection_log_timestamp"], errors="coerce")
    print("data_collection_log_timestamp min:", ts.min())
    print("data_collection_log_timestamp max:", ts.max())
else:
    print("data_collection_log_timestamp column not found or file has no rows")
