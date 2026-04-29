-- Summary: QA business and distribution checks for value constraints and day-over-day drift.
WITH current_day AS (
  SELECT
    COUNT(*) AS row_count,
    AVG(total_consumption_active_import) AS avg_consumption
  FROM {glue_database}.silver_smart_meter_half_hourly_clean
  WHERE collection_date = DATE '{run_date}'
),
previous_day AS (
  SELECT
    collection_date,
    COUNT(*) AS row_count,
    AVG(total_consumption_active_import) AS avg_consumption
  FROM {glue_database}.silver_smart_meter_half_hourly_clean
  WHERE collection_date < DATE '{run_date}'
  GROUP BY collection_date
  ORDER BY collection_date DESC
  LIMIT 1
),
rule_violations AS (
  SELECT
    SUM(CASE WHEN aggregated_device_count_active <= 0 THEN 1 ELSE 0 END) AS bad_active_devices,
    SUM(CASE WHEN total_consumption_active_import < 0 THEN 1 ELSE 0 END) AS bad_consumption,
    SUM(CASE WHEN consumption_per_active_device < 0 THEN 1 ELSE 0 END) AS bad_consumption_per_device
  FROM {glue_database}.silver_smart_meter_half_hourly_clean
  WHERE collection_date = DATE '{run_date}'
),
peak_violations AS (
  SELECT
    COUNT(*) AS bad_peak_rows
  FROM {glue_database}.gold_peak_demand_substation_day
  WHERE consumption_date = DATE '{run_date}'
    AND peak_consumption > daily_total_consumption
)
SELECT
  '{run_date}' AS run_date,
  rv.bad_active_devices,
  rv.bad_consumption,
  rv.bad_consumption_per_device,
  pv.bad_peak_rows,
  cd.row_count AS current_row_count,
  pd.row_count AS previous_row_count,
  CASE
    WHEN pd.row_count IS NULL OR pd.row_count = 0 THEN NULL
    ELSE ABS((cd.row_count - pd.row_count) / CAST(pd.row_count AS DOUBLE))
  END AS row_count_change_ratio,
  cd.avg_consumption AS current_avg_consumption,
  pd.avg_consumption AS previous_avg_consumption,
  CASE
    WHEN pd.avg_consumption IS NULL OR pd.avg_consumption = 0 THEN NULL
    ELSE ABS((cd.avg_consumption - pd.avg_consumption) / pd.avg_consumption)
  END AS avg_consumption_change_ratio,
  CASE
    WHEN rv.bad_active_devices = 0
      AND rv.bad_consumption = 0
      AND rv.bad_consumption_per_device = 0
      AND pv.bad_peak_rows = 0
      AND (pd.row_count IS NULL OR ABS((cd.row_count - pd.row_count) / CAST(pd.row_count AS DOUBLE)) <= 0.20)
      AND (pd.avg_consumption IS NULL OR ABS((cd.avg_consumption - pd.avg_consumption) / pd.avg_consumption) <= 0.30)
    THEN 'PASS'
    ELSE 'FAIL'
  END AS business_rule_status
FROM rule_violations rv
CROSS JOIN peak_violations pv
CROSS JOIN current_day cd
LEFT JOIN previous_day pd ON TRUE;
