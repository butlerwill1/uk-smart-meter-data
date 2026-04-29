-- Summary: QA null checks for required identifier, timestamp, and consumption columns.
SELECT
  '{run_date}' AS run_date,
  SUM(CASE WHEN secondary_substation_unique_id IS NULL THEN 1 ELSE 0 END) AS null_substation_id,
  SUM(CASE WHEN data_collection_log_timestamp IS NULL THEN 1 ELSE 0 END) AS null_timestamp,
  SUM(CASE WHEN total_consumption_active_import IS NULL THEN 1 ELSE 0 END) AS null_consumption,
  CASE
    WHEN
      SUM(CASE WHEN secondary_substation_unique_id IS NULL THEN 1 ELSE 0 END) = 0
      AND SUM(CASE WHEN data_collection_log_timestamp IS NULL THEN 1 ELSE 0 END) = 0
      AND SUM(CASE WHEN total_consumption_active_import IS NULL THEN 1 ELSE 0 END) = 0
    THEN 'PASS'
    ELSE 'FAIL'
  END AS null_check_status
FROM {glue_database}.silver_smart_meter_half_hourly_clean
WHERE collection_date = DATE '{run_date}';
