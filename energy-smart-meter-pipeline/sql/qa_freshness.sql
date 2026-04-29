-- Summary: QA freshness check to confirm data exists for the requested run date.
SELECT
  '{run_date}' AS run_date,
  COUNT(*) AS row_count,
  CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL' END AS freshness_status
FROM {glue_database}.silver_smart_meter_half_hourly_clean
WHERE collection_date = DATE '{run_date}';
