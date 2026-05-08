-- Summary: Highest-demand day at whole-system level and by DNO.
WITH daily AS (
  SELECT
    consumption_date,
    dno_alias,
    SUM(daily_total_consumption) AS system_daily_total,
    MAX(peak_consumption) AS max_substation_peak,
    COUNT(DISTINCT secondary_substation_unique_id) AS active_substations
  FROM energy_smart_meter.gold_peak_demand_substation_day
  GROUP BY 1, 2
)
SELECT
  consumption_date,
  dno_alias,
  system_daily_total,
  max_substation_peak,
  active_substations
FROM daily
ORDER BY system_daily_total DESC
LIMIT 20;
