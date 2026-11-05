-- Query 1. Schema on read: Athena reads the JSON files in place; this only describes them.
-- The dates stay strings: they are ISO 8601 in one format, so they sort correctly as text.
CREATE EXTERNAL TABLE IF NOT EXISTS lab8.payment_events (
  invoiceId     string,
  status        string,
  failureReason string,
  amount        bigint,
  finalAmount   bigint,
  ccy           int,
  reference     string,
  createdDate   string,
  modifiedDate  string,
  receivedAt    string,
  merchantId    string,
  merchantName  string,
  mcc           int,
  customerId    string,
  paymentMethod string,
  device        string
)
PARTITIONED BY (dt string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET}/payments/'
