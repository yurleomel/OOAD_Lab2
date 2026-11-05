-- Query 5. Payments per hour of the day, by the time the payment was created (UTC).
SELECT hour(from_iso8601_timestamp(createdDate)) AS hour_utc,
       COUNT(*) AS payments
FROM ${PAYMENTS}
GROUP BY 1
ORDER BY 1
