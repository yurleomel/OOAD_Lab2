-- The crawler's table: does it read, and do its int columns hold every value?
SELECT COUNT(*) AS events,
       COUNT(DISTINCT dt) AS partitions,
       COUNT(failurereason) AS with_failure_reason,
       MAX(amount) AS max_amount,
       MAX(finalamount) AS max_final_amount,
       2147483647 AS int_limit
FROM lab8_crawled.payments
