-- Summary: Compare mean load profile by weekday/weekend and half-hour slot.
WITH labeled AS (
  SELECT
    CASE WHEN day_of_week(consumption_date) IN (6, 7) THEN 'weekend' ELSE 'weekday' END AS day_type,
    half_hour_slot,
    avg_consumption
  FROM energy_smart_meter.gold_avg_load_profile_day
)
SELECT
  day_type,
  half_hour_slot,
  AVG(avg_consumption) AS mean_avg_consumption,
  COUNT(*) AS contributing_day_slots
FROM labeled
GROUP BY 1, 2
ORDER BY day_type, half_hour_slot;
