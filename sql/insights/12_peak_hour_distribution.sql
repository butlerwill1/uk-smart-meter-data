-- Summary: Distribution of hourly timing for daily peak events across substations.
SELECT
  hour(peak_timestamp) AS peak_hour,
  COUNT(*) AS substation_days
FROM energy_smart_meter.gold_peak_demand_substation_day
GROUP BY 1
ORDER BY 1;
