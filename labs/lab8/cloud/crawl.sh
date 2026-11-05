#!/usr/bin/env bash
# The Glue Crawler over what Firehose wrote, and the schema it found.
set -euo pipefail

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET=${LAB8_BUCKET:-peach-lab8-$ACCOUNT}
ROLE=peach-lab8-crawler # from ../athena/crawler.sh
CRAWLER=peach-lab8-stream
DATABASE=lab8_stream

aws iam put-role-policy --role-name "$ROLE" --policy-name read-stream --policy-document \
  "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/payments-stream/*\"}]}"

aws glue get-database --name "$DATABASE" >/dev/null 2>&1 ||
  aws glue create-database --database-input "{\"Name\":\"$DATABASE\"}"

aws glue get-crawler --name "$CRAWLER" >/dev/null 2>&1 ||
  aws glue create-crawler --name "$CRAWLER" --role "$ROLE" --database-name "$DATABASE" \
    --targets "{\"S3Targets\":[{\"Path\":\"s3://$BUCKET/payments-stream/\"}]}"

aws glue start-crawler --name "$CRAWLER"
until [ "$(aws glue get-crawler --name "$CRAWLER" --query Crawler.State --output text)" = READY ]; do
  sleep 10
done
aws glue get-crawler --name "$CRAWLER" --query 'Crawler.LastCrawl.Status' --output text
aws glue get-tables --database-name "$DATABASE" \
  --query 'TableList[].{Table:Name,Partitions:PartitionKeys[].Name,Columns:StorageDescriptor.Columns[].Name}' --output json
