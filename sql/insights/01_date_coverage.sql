-- Summary: Dataset coverage across gold tables (date range and number of populated days).
SELECT
  'gold_peak_demand_substation_day' AS table_name,
  MIN(consumption_date) AS min_date,
  MAX(consumption_date) AS max_date,
  COUNT(DISTINCT consumption_date) AS populated_days,
  COUNT(*) AS row_count
FROM energy_smart_meter.gold_peak_demand_substation_day
UNION ALL
SELECT
  'gold_avg_load_profile_day' AS table_name,
  MIN(consumption_date) AS min_date,
  MAX(consumption_date) AS max_date,
  COUNT(DISTINCT consumption_date) AS populated_days,
  COUNT(*) AS row_count
FROM energy_smart_meter.gold_avg_load_profile_day;
