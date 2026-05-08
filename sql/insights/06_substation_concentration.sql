-- Summary: Concentration of total demand among top substations (portfolio metric).
WITH substation_totals AS (
  SELECT
    secondary_substation_unique_id,
    SUM(daily_total_consumption) AS total_consumption
  FROM energy_smart_meter.gold_peak_demand_substation_day
  GROUP BY 1
), ranked AS (
  SELECT
    secondary_substation_unique_id,
    total_consumption,
    ROW_NUMBER() OVER (ORDER BY total_consumption DESC) AS rn,
    SUM(total_consumption) OVER () AS fleet_total_consumption
  FROM substation_totals
)
SELECT
  rn,
  secondary_substation_unique_id,
  total_consumption,
  fleet_total_consumption,
  total_consumption / NULLIF(fleet_total_consumption, 0) AS share_of_total
FROM ranked
WHERE rn <= 20
ORDER BY rn;
