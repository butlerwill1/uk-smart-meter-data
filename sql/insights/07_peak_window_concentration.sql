-- Summary: Share of substation-day peak events occurring during evening peak window vs overnight.
WITH h AS (
  SELECT hour(peak_timestamp) AS peak_hour, COUNT(*) AS n
  FROM energy_smart_meter.gold_peak_demand_substation_day
  GROUP BY 1
), t AS (
  SELECT SUM(n) AS total_n FROM h
)
SELECT
  SUM(CASE WHEN peak_hour BETWEEN 17 AND 20 THEN n ELSE 0 END) AS evening_peak_events,
  SUM(CASE WHEN peak_hour BETWEEN 17 AND 20 THEN n ELSE 0 END) / CAST(MAX(total_n) AS DOUBLE) AS evening_peak_share,
  SUM(CASE WHEN peak_hour BETWEEN 0 AND 5 THEN n ELSE 0 END) AS overnight_peak_events,
  SUM(CASE WHEN peak_hour BETWEEN 0 AND 5 THEN n ELSE 0 END) / CAST(MAX(total_n) AS DOUBLE) AS overnight_peak_share,
  MAX(total_n) AS total_events
FROM h CROSS JOIN t;
