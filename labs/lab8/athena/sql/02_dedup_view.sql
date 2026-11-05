-- Query 2. One row per payment: its latest status.
-- The inner SELECT removes the exact duplicates; then row_number() ranks what is left.
CREATE OR REPLACE VIEW lab8.payments AS
SELECT invoiceId, status, failureReason, amount, finalAmount, ccy, reference,
       createdDate, modifiedDate, receivedAt,
       merchantId, merchantName, mcc, customerId, paymentMethod, device, dt
FROM (
  SELECT *, row_number() OVER (PARTITION BY invoiceId ORDER BY modifiedDate DESC) AS rn
  FROM (SELECT DISTINCT * FROM lab8.payment_events)
)
WHERE rn = 1
