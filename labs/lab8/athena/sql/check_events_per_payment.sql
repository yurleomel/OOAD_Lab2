-- How many distinct events does a payment have?
SELECT events_in_payment, COUNT(*) AS payments
FROM (SELECT invoiceId, COUNT(*) AS events_in_payment FROM (SELECT DISTINCT * FROM lab8.payment_events) GROUP BY 1)
GROUP BY 1
ORDER BY 1
