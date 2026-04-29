-- Summary: Create Athena external gold table for peak demand per substation per day.
CREATE EXTERNAL TABLE IF NOT EXISTS {glue_database}.gold_peak_demand_substation_day (
  dno_alias STRING,
  secondary_substation_unique_id STRING,
  peak_consumption DOUBLE,
  peak_timestamp TIMESTAMP,
  daily_total_consumption DOUBLE,
  avg_half_hour_consumption DOUBLE,
  avg_active_devices DOUBLE,
  feeder_count BIGINT,
  reading_count BIGINT
)
PARTITIONED BY (consumption_date DATE)
STORED AS PARQUET
LOCATION 's3://REPLACE_DATA_BUCKET/portfolio/energy/gold/gold_peak_demand_substation_day/'
TBLPROPERTIES ('parquet.compress'='SNAPPY');
