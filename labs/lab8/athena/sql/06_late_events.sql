-- Query 6. Lateness is a property of an event, so this reads the events, not the payments view:
-- the view keeps only the last event of each payment. DISTINCT drops the exact duplicates.
WITH delays AS (
  SELECT date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) AS delay_s
  FROM (SELECT DISTINCT * FROM lab8.payment_events)
)
SELECT COUNT(*) AS events,
       COUNT_IF(delay_s > 60) AS late_over_60s,
       ROUND(CAST(COUNT_IF(delay_s > 60) AS double) / COUNT(*) * 100, 3) AS late_over_60s_pct,
       COUNT_IF(delay_s > 3600) AS late_over_1h,
       ROUND(CAST(COUNT_IF(delay_s > 3600) AS double) / COUNT(*) * 100, 3) AS late_over_1h_pct,
       MIN(delay_s) AS min_delay_s,
       approx_percentile(delay_s, 0.5) AS median_delay_s,
       MAX(delay_s) AS max_delay_s
FROM delays
