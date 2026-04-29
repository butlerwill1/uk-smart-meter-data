-- Summary: QA uniqueness checks for gold tables by business key.
WITH peak_dupes AS (
  SELECT
    consumption_date,
    secondary_substation_unique_id,
    COUNT(*) AS c
  FROM {glue_database}.gold_peak_demand_substation_day
  WHERE consumption_date = DATE '{run_date}'
  GROUP BY 1,2
  HAVING COUNT(*) > 1
),
profile_dupes AS (
  SELECT
    consumption_date,
    half_hour_slot,
    COUNT(*) AS c
  FROM {glue_database}.gold_avg_load_profile_day
  WHERE consumption_date = DATE '{run_date}'
  GROUP BY 1,2
  HAVING COUNT(*) > 1
)
SELECT
  '{run_date}' AS run_date,
  (SELECT COUNT(*) FROM peak_dupes) AS peak_duplicate_key_count,
  (SELECT COUNT(*) FROM profile_dupes) AS profile_duplicate_key_count,
  CASE
    WHEN (SELECT COUNT(*) FROM peak_dupes) = 0 AND (SELECT COUNT(*) FROM profile_dupes) = 0
    THEN 'PASS'
    ELSE 'FAIL'
  END AS uniqueness_status;
