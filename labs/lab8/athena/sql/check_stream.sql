-- What came through Kinesis and Firehose, per replayed slice. The producer sent 1183, 1292 and 1342 events.
SELECT substr(receivedat, 12, 4) || '0' AS slice,
       COUNT(*) AS events,
       COUNT(DISTINCT invoiceid) AS payments,
       COUNT_IF(status = 'failure') AS failed,
       COUNT_IF(status = 'success') AS succeeded,
       ROUND(100.0 * COUNT_IF(status = 'failure') / COUNT_IF(status IN ('success', 'failure')), 2) AS failed_pct
FROM lab8_stream.payments_stream
WHERE dt = '2026-11-05'
GROUP BY 1
ORDER BY 1
