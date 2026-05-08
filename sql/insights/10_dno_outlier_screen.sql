-- Summary: Screen for highly skewed substation distributions using DNO mean-to-median ratio.
WITH s AS (
  SELECT
    dno_alias,
    secondary_substation_unique_id,
    AVG(daily_total_consumption) AS mean_daily_total
  FROM energy_smart_meter.gold_peak_demand_substation_day
  GROUP BY 1,2
), d AS (
  SELECT
    dno_alias,
    AVG(mean_daily_total) AS dno_mean,
    APPROX_PERCENTILE(mean_daily_total, 0.5) AS dno_median
  FROM s
  GROUP BY 1
)
SELECT
  dno_alias,
  dno_mean,
  dno_median,
  dno_mean / NULLIF(dno_median,0) AS mean_to_median_ratio
FROM d
ORDER BY mean_to_median_ratio DESC;
