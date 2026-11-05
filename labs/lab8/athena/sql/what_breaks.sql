-- What goes wrong without deduplication, measured.
WITH raw_success AS (SELECT * FROM lab8.payment_events WHERE status = 'success')
SELECT 'payments, COUNT(*) on raw events' AS measure, CAST(COUNT(*) AS varchar) AS value FROM lab8.payment_events
UNION ALL SELECT 'payments, COUNT(*) on the view', CAST(COUNT(*) AS varchar) FROM lab8.payments
UNION ALL SELECT 'UAH turnover on raw events', CAST(CAST(SUM(finalAmount) AS decimal(20, 2)) / 100 AS varchar) FROM raw_success WHERE ccy = 980
UNION ALL SELECT 'UAH turnover on the view', CAST(CAST(SUM(finalAmount) AS decimal(20, 2)) / 100 AS varchar) FROM lab8.payments WHERE status = 'success' AND ccy = 980
UNION ALL SELECT 'failure % on raw events', CAST(ROUND(CAST(COUNT_IF(status = 'failure') AS double) / COUNT(*) * 100, 2) AS varchar) FROM lab8.payment_events
UNION ALL SELECT 'failure % on the view', CAST(ROUND(CAST(COUNT_IF(status = 'failure') AS double) / COUNT(*) * 100, 2) AS varchar) FROM lab8.payments
UNION ALL SELECT 'DISTINCT and row_number() on one level: rows left', CAST(COUNT(*) AS varchar) FROM (
  SELECT DISTINCT *, row_number() OVER (PARTITION BY invoiceId ORDER BY modifiedDate DESC) AS rn FROM lab8.payment_events)
UNION ALL SELECT 'rank() = 1 with no DISTINCT: rows left', CAST(COUNT(*) AS varchar) FROM (
  SELECT rank() OVER (PARTITION BY invoiceId ORDER BY modifiedDate DESC) AS r FROM lab8.payment_events) WHERE r = 1
UNION ALL SELECT 'row_number() = 1 with no DISTINCT: rows left', CAST(COUNT(*) AS varchar) FROM (
  SELECT row_number() OVER (PARTITION BY invoiceId ORDER BY modifiedDate DESC) AS r FROM lab8.payment_events) WHERE r = 1
