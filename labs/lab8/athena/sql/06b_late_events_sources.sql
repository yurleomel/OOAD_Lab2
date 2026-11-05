-- The same count on three inputs, to show what the choice of input changes.
SELECT 'raw events' AS source, COUNT(*) AS events,
       COUNT_IF(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 60) AS late_over_60s
FROM lab8.payment_events
UNION ALL
SELECT 'distinct events', COUNT(*),
       COUNT_IF(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 60)
FROM (SELECT DISTINCT * FROM lab8.payment_events)
UNION ALL
SELECT 'payments view (last event only)', COUNT(*),
       COUNT_IF(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 60)
FROM lab8.payments
