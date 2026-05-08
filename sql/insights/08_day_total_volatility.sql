-- Summary: Day-to-day system total volatility using coefficient of variation.
WITH d AS (
  SELECT consumption_date, SUM(daily_total_consumption) AS day_total
  FROM energy_smart_meter.gold_peak_demand_substation_day
  GROUP BY 1
)
SELECT
  COUNT(*) AS days,
  AVG(day_total) AS mean_day_total,
  STDDEV_POP(day_total) AS stddev_day_total,
  STDDEV_POP(day_total) / NULLIF(AVG(day_total), 0) AS cv_day_total
FROM d;
