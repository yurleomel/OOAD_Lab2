-- Public, small dataset. Run a dry run first and set maximum bytes billed.
-- A row limit alone does not limit bytes scanned.
SELECT
  corpus,
  SUM(word_count) AS total_words
FROM `bigquery-public-data.samples.shakespeare`
GROUP BY corpus
ORDER BY total_words DESC
LIMIT 10;
