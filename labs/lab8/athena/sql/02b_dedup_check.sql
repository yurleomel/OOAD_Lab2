-- The result of the view: one million rows, each in a final status.
SELECT status, COUNT(*) AS payments, COUNT(DISTINCT invoiceId) AS unique_invoices
FROM lab8.payments
GROUP BY status
ORDER BY payments DESC
