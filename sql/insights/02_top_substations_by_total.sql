-- Summary: Top substations by average daily total consumption and peak demand.
SELECT
  dno_alias,
  secondary_substation_unique_id,
  COUNT(*) AS active_days,
  AVG(daily_total_consumption) AS avg_daily_total_consumption,
  MAX(peak_consumption) AS max_observed_peak,
  AVG(peak_consumption) AS avg_peak_consumption
FROM energy_smart_meter.gold_peak_demand_substation_day
GROUP BY 1, 2
ORDER BY avg_daily_total_consumption DESC
LIMIT 15;
