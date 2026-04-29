-- Summary: Create Athena external table over read-only external Bronze smart meter parquet dataset.
CREATE EXTERNAL TABLE IF NOT EXISTS {glue_database}.raw_external_smart_meter (
  dataset_id STRING,
  dno_alias STRING,
  aggregated_device_count_active BIGINT,
  total_consumption_active_import DOUBLE,
  data_collection_log_timestamp TIMESTAMP,
  geometry STRING,
  secondary_substation_unique_id STRING,
  lv_feeder_unique_id STRING,
  bbox STRING
)
STORED AS PARQUET
LOCATION 's3://weave.energy/smart-meter.parquet'
TBLPROPERTIES ('parquet.compress'='SNAPPY');
