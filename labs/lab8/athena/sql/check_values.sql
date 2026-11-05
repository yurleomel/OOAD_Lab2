-- Every value of the categorical fields and how often: spots typos, nulls and odd currencies.
SELECT 'status' AS field, status AS value, COUNT(*) AS n FROM lab8.payment_events GROUP BY 2
UNION ALL SELECT 'ccy', CAST(ccy AS varchar), COUNT(*) FROM lab8.payment_events GROUP BY 2
UNION ALL SELECT 'paymentMethod', paymentMethod, COUNT(*) FROM lab8.payment_events GROUP BY 2
UNION ALL SELECT 'device', device, COUNT(*) FROM lab8.payment_events GROUP BY 2
UNION ALL SELECT 'merchant', merchantId || ' ' || merchantName || ' mcc ' || CAST(mcc AS varchar), COUNT(*) FROM lab8.payment_events GROUP BY 2
UNION ALL SELECT 'failureReason', failureReason, COUNT(*) FROM lab8.payment_events GROUP BY 2
ORDER BY 1, 3 DESC
