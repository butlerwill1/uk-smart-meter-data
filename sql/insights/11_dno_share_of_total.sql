-- Summary: Share of total demand by DNO for portfolio segmentation analysis.
SELECT
  dno_alias,
  SUM(daily_total_consumption) AS total_consumption,
  SUM(daily_total_consumption) / SUM(SUM(daily_total_consumption)) OVER () AS share_of_total
FROM energy_smart_meter.gold_peak_demand_substation_day
GROUP BY 1
ORDER BY total_consumption DESC;
