-- The answers about scale.
SELECT COUNT(*) AS events,
       COUNT(DISTINCT invoiceId) AS unique_invoices,
       COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM lab8.payment_events)) AS exact_duplicates
FROM lab8.payment_events
