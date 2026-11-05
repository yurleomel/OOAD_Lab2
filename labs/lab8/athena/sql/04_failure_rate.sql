-- Query 4. Share of failed payments per payment method and device, highest first.
SELECT paymentMethod,
       device,
       COUNT(*) AS payments,
       COUNT_IF(status = 'failure') AS failed,
       ROUND(CAST(COUNT_IF(status = 'failure') AS double) / COUNT(*) * 100, 2) AS failure_pct
FROM ${PAYMENTS}
GROUP BY paymentMethod, device
ORDER BY failure_pct DESC, paymentMethod, device
