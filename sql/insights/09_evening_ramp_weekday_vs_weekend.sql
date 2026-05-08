-- Summary: Compare evening demand intensity against overnight baseline for weekdays vs weekends.
WITH labeled AS (
  SELECT
    CASE WHEN day_of_week(consumption_date) IN (6, 7) THEN 'weekend' ELSE 'weekday' END AS day_type,
    half_hour_slot,
    avg_consumption
  FROM energy_smart_meter.gold_avg_load_profile_day
), agg AS (
  SELECT
    day_type,
    AVG(CASE WHEN half_hour_slot BETWEEN 34 AND 41 THEN avg_consumption END) AS evening_avg,
    AVG(CASE WHEN half_hour_slot BETWEEN 4 AND 11 THEN avg_consumption END) AS night_avg
  FROM labeled
  GROUP BY 1
)
SELECT
  day_type,
  evening_avg,
  night_avg,
  evening_avg / NULLIF(night_avg, 0) AS evening_to_night_ratio
FROM agg;
