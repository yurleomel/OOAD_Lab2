#!/usr/bin/env bash
# Way B: a Glue Crawler over payments/, writing into its own database so that it does not touch
# the hand-written table. Prints the schema it inferred.
set -euo pipefail

BUCKET=peach-lab8-$(aws sts get-caller-identity --query Account --output text)
ROLE=peach-lab8-crawler
CRAWLER=peach-lab8-payments
DATABASE=lab8_crawled

if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --output text --query Role.Arn \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"glue.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
  aws iam attach-role-policy --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole
  aws iam put-role-policy --role-name "$ROLE" --policy-name read-payments --policy-document \
    "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/payments/*\"},{\"Effect\":\"Allow\",\"Action\":\"s3:ListBucket\",\"Resource\":\"arn:aws:s3:::$BUCKET\"}]}"
  sleep 15 # IAM needs a moment before Glue can assume a new role
fi

aws glue get-database --name "$DATABASE" >/dev/null 2>&1 ||
  aws glue create-database --database-input "{\"Name\":\"$DATABASE\"}"

aws glue get-crawler --name "$CRAWLER" >/dev/null 2>&1 ||
  aws glue create-crawler --name "$CRAWLER" --role "$ROLE" --database-name "$DATABASE" \
    --targets "{\"S3Targets\":[{\"Path\":\"s3://$BUCKET/payments/\"}]}"

aws glue start-crawler --name "$CRAWLER"
echo "crawler started"
until [ "$(aws glue get-crawler --name "$CRAWLER" --query Crawler.State --output text)" = READY ]; do
  sleep 15
done

aws glue get-crawler --name "$CRAWLER" --query 'Crawler.LastCrawl.{Status:Status,Error:ErrorMessage}' --output json
aws glue get-crawler-metrics --crawler-name-list "$CRAWLER" \
  --query 'CrawlerMetricsList[0].{tablesCreated:TablesCreated,seconds:LastRuntimeSeconds}' --output json
aws glue get-tables --database-name "$DATABASE" \
  --query 'TableList[].{Table:Name,Partitions:PartitionKeys,Columns:StorageDescriptor.Columns,SerDe:StorageDescriptor.SerdeInfo.SerializationLibrary}' --output json
