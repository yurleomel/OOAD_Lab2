-- Query 3. Turnover by merchant and currency, successful payments only, in major units.
-- decimal keeps the kopiyky exact: bigint / 100 would drop them, and double would round them.
SELECT merchantId,
       merchantName,
       CASE ccy WHEN 980 THEN 'UAH' WHEN 840 THEN 'USD' WHEN 978 THEN 'EUR' END AS currency,
       COUNT(*) AS payments,
       CAST(SUM(finalAmount) AS decimal(20, 2)) / 100 AS turnover
FROM ${PAYMENTS}
WHERE status = 'success'
GROUP BY 1, 2, 3
ORDER BY merchantId, currency
