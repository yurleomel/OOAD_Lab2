-- Know the data before trusting a query on it: what counts as a duplicate, ties, what dt means.
WITH e AS (SELECT * FROM lab8.payment_events)
SELECT
  (SELECT COUNT(*) FROM e) AS events,
  (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM e)) AS distinct_rows,
  (SELECT COUNT(*) FROM (SELECT DISTINCT invoiceId, status, modifiedDate, receivedAt, finalAmount, failureReason FROM e)) AS distinct_without_dt,
  (SELECT COUNT(*) FROM (SELECT DISTINCT invoiceId, status, modifiedDate FROM e)) AS distinct_invoice_status_time,
  (SELECT COUNT(*) FROM (SELECT DISTINCT invoiceId, status FROM e)) AS distinct_invoice_status,
  (SELECT COUNT(DISTINCT invoiceId) FROM e) AS invoices,
  (SELECT COUNT(*) FROM e WHERE invoiceId IS NULL OR status IS NULL OR modifiedDate IS NULL OR receivedAt IS NULL) AS null_keys,
  (SELECT COUNT(*) FROM e WHERE dt = substr(modifiedDate, 1, 10)) AS dt_is_modified_date,
  (SELECT COUNT(*) FROM e WHERE dt = substr(receivedAt, 1, 10)) AS dt_is_received_date,
  (SELECT COUNT(*) FROM e WHERE dt = substr(createdDate, 1, 10)) AS dt_is_created_date,
  (SELECT MIN(createdDate) FROM e) AS first_created,
  (SELECT MAX(createdDate) FROM e) AS last_created,
  (SELECT MAX(receivedAt) FROM e) AS last_received,
  (SELECT COUNT(*) FROM (SELECT invoiceId, modifiedDate FROM e GROUP BY 1, 2 HAVING COUNT(DISTINCT status) > 1)) AS invoice_times_with_two_statuses,
  (SELECT COUNT(*) FROM e WHERE receivedAt < modifiedDate) AS received_before_modified
