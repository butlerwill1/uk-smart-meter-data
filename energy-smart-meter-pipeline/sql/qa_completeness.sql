-- Summary: QA completeness checks for expected 48 half-hour slots and timestamp coverage.
WITH slots AS (
  SELECT half_hour_slot
  FROM {glue_database}.gold_avg_load_profile_day
  WHERE consumption_date = DATE '{run_date}'
),
expected AS (
  SELECT seq AS half_hour_slot FROM UNNEST(SEQUENCE(0, 47)) AS t(seq)
),
missing AS (
  SELECT e.half_hour_slot
  FROM expected e
  LEFT JOIN slots s ON s.half_hour_slot = e.half_hour_slot
  WHERE s.half_hour_slot IS NULL
),
ts_check AS (
  SELECT
    COUNT(DISTINCT DATE_FORMAT(data_collection_log_timestamp, '%H:%i')) AS distinct_times
  FROM {glue_database}.silver_smart_meter_half_hourly_clean
  WHERE collection_date = DATE '{run_date}'
)
SELECT
  '{run_date}' AS run_date,
  (SELECT COUNT(*) FROM slots) AS slot_rows,
  (SELECT COUNT(*) FROM missing) AS missing_slot_count,
  (SELECT distinct_times FROM ts_check) AS distinct_timestamp_count,
  CASE
    WHEN (SELECT COUNT(*) FROM missing) = 0 AND (SELECT distinct_times FROM ts_check) = 48
    THEN 'PASS'
    ELSE 'FAIL'
  END AS completeness_status;
