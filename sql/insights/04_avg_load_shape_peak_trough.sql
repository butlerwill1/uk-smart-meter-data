-- Summary: Average load shape by half-hour slot across all available days.
SELECT
  hour_of_day,
  minute_of_hour,
  half_hour_slot,
  AVG(avg_consumption) AS mean_slot_consumption,
  AVG(total_consumption) AS mean_slot_total_consumption,
  SUM(reading_count) AS total_readings
FROM energy_smart_meter.gold_avg_load_profile_day
GROUP BY 1, 2, 3
ORDER BY mean_slot_consumption DESC;
