-- Summary: Create Athena external gold table for average daily half-hour load shape.
CREATE EXTERNAL TABLE IF NOT EXISTS {glue_database}.gold_avg_load_profile_day (
  hour_of_day INT,
  minute_of_hour INT,
  half_hour_slot INT,
  avg_consumption DOUBLE,
  total_consumption DOUBLE,
  reading_count BIGINT,
  substation_count BIGINT,
  feeder_count BIGINT,
  avg_consumption_per_active_device DOUBLE
)
PARTITIONED BY (consumption_date DATE)
STORED AS PARQUET
LOCATION 's3://REPLACE_DATA_BUCKET/portfolio/energy/gold/gold_avg_load_profile_day/'
TBLPROPERTIES ('parquet.compress'='SNAPPY');
