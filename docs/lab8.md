# Lab 8 — Big Data on AWS: the Uklon example

The code is in `labs/lab8/`: `athena/` (Part 2), `streaming/` (Part 3), `cloud/` (Part 4). This file
holds the answers, the measured numbers and what was found on the way.

## Part 1 — Uklon's architecture

**The real-time road falls behind by 10 minutes; the batch road by a day.** Ten minutes behind on the
real-time road is an outage the rider can feel: surge is priced for the city as it was 10 minutes
ago, and matching reads driver positions from Redis that are several kilometres out of date, so the
ETA and the offered driver are wrong. Rides still happen, because orders go through Fargate and
Aurora and not through the stream. Nothing is lost: Kinesis keeps the events and Flink catches up
from its checkpoint, but the decisions already made on stale data stay made. A day behind on the
batch road is a ticket, not an incident: dashboards show the day before yesterday and models train
on older data, no rider notices, and the raw files wait safely in S3 for the next run. On the first
road freshness is the product, on the second completeness is.

**Why GPS does not go through Lambda.** 580 million pings a day is about 6,700 a second on average,
and several times that at peak. Through API Gateway and Lambda that means one invocation per ping:
roughly $0.20 per million requests plus duration on Lambda, $1 per million on the cheapest API
Gateway, so about $20,000 a month before any work is done, and hundreds of concurrent executions
against a default quota of 1,000. It would also be one HTTPS request every 3 seconds from every
driver's phone, where a persistent MQTT connection costs far less battery and traffic. And a ping
needs no code of its own: it only has to land in the log, and Flink then reads thousands at a time.
Lambda fits what happens rarely, which is why the diagram uses it for new files.

**What a small startup drops first.**

| Dropped first | Instead | What it loses |
|---|---|---|
| SageMaker | ETA from a routing API, no demand forecast | ETA tuned to its own city; positioning drivers ahead of demand |
| Managed Flink, DynamoDB | a fixed price, or surge recomputed by a cron job each minute | surge that reacts in seconds; live alerts |
| Kinesis, Firehose, DMS | events written straight to S3, or no event stream at all | replay; many independent readers of one log; the database and the analytics are coupled |
| Glue, Parquet, Athena, Quick | SQL on a read replica, with Metabase | cheap scans over long history; analysts share a database with production |
| IoT Core | an HTTP call every 10 s from a few hundred drivers | the cost curve at scale, and fresher positions |

What stays: the load balancer, one service on Fargate, a relational database, Redis for positions
(matching cannot work without them) and push notifications. All the dropped parts can be added
later only if the raw events were kept, so the one cheap thing worth doing from the first day is to
write them to S3.

## Part 2 — Batch on AWS

Queries: `labs/lab8/athena/sql/`, numbered as in the lab. Every result: `labs/lab8/athena/results/`.
`run.py` sends a query and records its time and scan in `results/stats.csv`.

### The data

Checked before trusting any query on it (`check_data.sql`, `check_values.sql`):

- Every payment has exactly 3 events after deduplication, and no two events of a payment share a
  `modifiedDate`, so "the latest event" is never a tie.
- A duplicate is identical in every field, `receivedAt` included.
- `dt` is the date of `modifiedDate`: true for all 3,030,197 rows. Payments are created up to
  30 October 23:59:58, so `dt=2026-10-31` is a 2 KB file of the events that finished after midnight.
- No event was received before it happened.

### Answers about scale

| | |
|---|---|
| Events (`COUNT(*)`, query 1) | 3,030,197 in 31 partitions |
| Unique `invoiceId` | **1,000,000** |
| Exact duplicates | **30,197** (1.00% of the events) |
| Events more than an hour late | **0 of 3,000,000: 0%** (the largest delay is 600 s) |
| Events more than 60 s late (query 6) | **60,231 of 3,000,000: 2.008%** |

Query 6 reads the distinct events and not the `payments` view, although the lab says every query
reads the view: lateness belongs to an event, and the view keeps only the last event of each payment.
On the view the answer would be 20,196 of 1,000,000; on the raw table 60,824 of 3,030,197.

### Results of queries 2–6

**Query 2, the view:** 1,000,000 rows, 939,820 `success` and 60,180 `failure`, nothing left in
`created` or `processing`.

**Query 3, turnover** in major units. All 30 rows are in `results/03_turnover.json.csv`. UAH only:

| Merchant | Payments | UAH |
|---|---|---|
| m-009 Інтернет-магазин | 87,115 | 310,259,259.21 |
| m-008 АЗС | 87,560 | 144,641,341.06 |
| m-010 Квитки | 87,303 | 77,749,863.65 |
| m-002 Супермаркет | 87,283 | 54,147,597.02 |
| m-004 Доставка їжі | 87,820 | 46,044,018.26 |
| m-007 Аптека | 87,374 | 38,554,151.04 |
| m-003 Таксі | 87,307 | 21,528,219.39 |
| m-005 Онлайн-кінотеатр | 87,357 | 13,016,193.00 |
| m-001 Кав'ярня | 87,637 | 11,435,687.68 |
| m-006 Музичний сервіс | 87,517 | 8,664,183.00 |

**Query 4, failure rate**, highest first:

| Method | Device | Payments | Failed | % |
|---|---|---|---|---|
| qr | android | 6,675 | 448 | 6.71 |
| apple_pay | android | 83,677 | 5,130 | 6.13 |
| google_pay | web | 59,996 | 3,645 | 6.08 |
| apple_pay | ios | 83,164 | 5,025 | 6.04 |
| card | android | 183,332 | 11,079 | 6.04 |
| card | web | 183,435 | 11,020 | 6.01 |
| google_pay | ios | 59,761 | 3,590 | 6.01 |
| qr | web | 6,669 | 400 | 6.00 |
| google_pay | android | 59,450 | 3,563 | 5.99 |
| apple_pay | web | 83,505 | 4,966 | 5.95 |
| card | ios | 183,541 | 10,912 | 5.95 |
| qr | ios | 6,795 | 402 | 5.92 |

Every row is close to 6%: no method or device stands out. `qr android` is on top with the smallest
sample, which is where a difference this size is most likely to be chance.

**Query 5, peak hours**, UTC, by `createdDate`. Three peaks: 18:00 (80,338), 12:00 (66,304) and
08:00 (59,947); quietest around 00:00–04:00, about 6,600 an hour. All 24 rows are in
`results/05_peak_hours.json.csv`.

**Query 6, late events:** above.

### JSON against Parquet

Queries 3–5, three runs each, median time. Both formats returned identical results (compared with
`diff`).

| Query | JSON scanned | JSON time | Parquet scanned | Parquet time | Scanned, times less |
|---|---|---|---|---|---|
| 3 turnover | 1,202.3 MB | 3.16 s | 6.11 MB | 1.29 s | 197 |
| 4 failure rate | 1,202.3 MB | 3.96 s | 0.64 MB | 1.15 s | 1,887 |
| 5 peak hours | 1,202.3 MB | 3.37 s | 6.25 MB | 1.53 s | 192 |

**In money it got 120 times cheaper, not 192–1,887 times:** Athena bills at least 10 MB per query, so
each Parquet query costs $0.000048 against $0.00573 on JSON. The files shrank from 1,261 MB to
83 MB. Not all of this is the format, because the Parquet table also holds one row per payment where
the JSON holds three events and repeats the deduplication in every query. Query 4 scans the least
since it reads only `status`, `paymentMethod` and `device`, three columns with a handful of values
that compress to almost nothing.

### Why `DISTINCT` comes before `row_number()`

SQL computes window functions before `DISTINCT`. Put on one level, `row_number()` gives each copy of a
row a different number, the copies are no longer identical, and `DISTINCT` removes nothing: measured,
**3,030,197 rows remain out of 3,030,197**. So the exact duplicates have to go in an inner query.

What breaks without deduplication (`what_breaks.sql`):

| | Raw events | Deduplicated |
|---|---|---|
| Number of payments, `COUNT(*)` | 3,030,197 | 1,000,000 |
| UAH turnover | 733,128,678.76 | 726,040,513.31 (the raw figure is 7,088,165.45 too high, +0.98%) |
| Failure share | 2.01% | 6.02% (`created` and `processing` dilute it) |
| Latest event with `rank() = 1` | 1,009,978 | 1,000,000 (9,978 payments whose last event arrived twice) |

One measured nuance: `row_number() = 1` alone also returns 1,000,000, because the copies are
identical and either one will do. On this data `DISTINCT` is what protects `rank()` and any query that
counts events, as query 6 does.

### Way B — Glue Crawler

`athena/crawler.sh`; it finished in 40 s and created `lab8_crawled.payments`.

- **Types.** `amount`, `finalamount`, `ccy` and `mcc` are `int`; I wrote `bigint` for the amounts. The
  dates are `string`, the same as mine. **`dt` was recognised as a partition** (`string`, all 31),
  because the folders are named `dt=...`.
- **`failureReason`** became an ordinary nullable `string`, the last column, since the crawler met it
  late and merged it in. It is filled on 60,779 of 3,030,197 rows and NULL on the rest. Names are all
  lower case.
- **Which is more convenient.** The crawler's, for exploring: no DDL, and it finds new partitions and
  fields by itself. Hand-written schemas stay common because a crawler guesses from a sample. `int`
  holds today's largest amount of 8,004,389 but stops at 21.4 million UAH; a later run may change a
  type or split one table in two, without review, and break the views on top. Its row estimate is a
  guess too: 1,202,922 against the real 3,030,197. A hand-written schema is a contract kept in Git.

## Part 3 — Streaming locally

`labs/lab8/streaming/`: `docker-compose.yml`, `producer.py`, `consumer.py`, with the logs in `output/`.
The day is 15 October: 101,788 events, 33,568 payments, replayed at 20 payments a second in 28 minutes.

The share counts only `success` and `failure`: `created` and `processing` are not outcomes yet. A window
closes 2 minutes of event time after it ends. The watermark is the newest event time per partition,
and the slowest partition sets it; with one global maximum, a consumer catching up reads a whole batch
from one partition first, and everything still waiting in the others looks late.

Experiments 2 and 4 read one replay of the day next to the baseline: each group has its own place in
the log. Experiments 1 and 3 replay 17:00–19:00 (15,199 events). `output/summary.txt` has all the numbers,
compared with the day counted straight from the file, where nothing can be late.

**Baseline.**

| | Consumer | True |
|---|---|---|
| Messages read | 101,788 | 101,788 |
| Duplicates dropped | 1,085 | |
| Rejected as late | 1,587 events | 0 |
| Payments in windows | 33,007 | 33,568 |
| Failed | 5.96% | 6.02% |
| Window and method pairs that differ | 505 of 4,437 | |

The price of an answer in seconds: 561 payments (1.7%) arrived after their window was closed. The batch
road counts them all.

**Experiment 1: stop for a minute, start again.** No message was lost, against a consumer that kept
running on the same replay:

| | Kept running | Stopped for a minute |
|---|---|---|
| Messages read | 15,199 | 15,199 |
| Payments in windows | 4,924 | 4,851 |
| Rejected as late | 234 | 202 |
| Windows that differ | | 13 of 430 |

The group stopped at offsets 1722, 1906 and 1730 and resumed at 1723, 1907 and 1731, with no gap. Its lag
was 3,503 while stopped and 298 fifteen seconds after the restart. Yet 73 payments are missing from the
windows: **the log kept the messages, but the counts of the open windows lived in the process**, and the
offsets had already moved past them. This is what Flink's checkpoints solve, saving state and offsets
together.

An earlier version of the consumer really did lose one event of 101,788 here: the stop signal raised an
exception just after `poll()` had taken a message, and its offset had already been stored. The signal now
only sets a flag, so the current message is finished first.

**Experiment 2: two consumers in one group.** See the Console screenshot. The first consumer held
partitions 0, 1 and 2; when the second joined, it kept 0 and 1, and the second took 2 from offset 641.
Together they read all 101,788 messages and dropped the same 1,085 duplicates, because the key sends every
copy of a payment to one partition. Each consumer computes only its own share of a window, so the two add
up to 1,341 alerts against 882 for one consumer: scaling out this way needs a step that merges the
windows.

**Experiment 3: 30% of the payments made to fail**, on top of the natural 6%. Same hours, without and with
the failures:

| | Normal | With failures |
|---|---|---|
| Failed | 5.87% | 33.49% |
| Alerts, of 430 window and method pairs | 99 | 370 |
| Alerts in windows of 10+ payments | 40 | 212 |

**Experiment 4: no waiting for late events.**

| | Grace 2 min | Grace 0 |
|---|---|---|
| Rejected as late | 1,587 | 1,973 |
| Payments in windows | 33,007 | 32,875 |
| Windows that differ from the truth | 505 | 609 |
| Failed overall | 5.96% | 5.96% |

Fewer extra rejections than expected, only 386: most late events are 1–10 minutes late and miss a
2-minute grace period anyway, and a watermark set by the slowest partition already gives ordinary events
a few seconds. The overall share does not move, because lateness here does not depend on the outcome; the
damage is in individual windows.

**What the alert shows.** On a normal day the rule fires 882 times, on 20% of the 4,421 windows that
closed, while the true rate is 6%. With about 23 payments a minute split over four methods, a window holds
too few payments for a 10% threshold: one failure out of six is already an alert. Only 236 of the 882 are
in windows of at least 10 payments. A real alert needs a longer window or a minimum sample.

**The set of seen events** reached 100,703 entries in one day, so about 3 million a month, growing without
limit. A duplicate arrives close to its original, so Redis or Flink state with a TTL of about an hour would
catch them at a fixed size. The price: a duplicate older than the TTL gets through.

## Part 4 — Streaming in the cloud

**Not run yet: Kinesis and Firehose are not available on the AWS Free plan.** The code is ready and
planned: 12 resources to add, nothing changed or destroyed.

Same payments dataset. `infra/lab8/` holds the stream, Firehose, the Lambda check and the SNS topic, in
the same Terraform workspace as the rest of the project, so the change is reviewed as a plan on a pull
request and applied on merge. `lab8_stream_enabled` in `infra/terraform.tfvars` is off by default: one pull
request switches the pipeline on, the next removes it, and no stream is left running. The bucket, the
crawler (`labs/lab8/cloud/crawl.sh`) and the Athena tables stay outside the switch, so the data can still
be read afterwards. The producer is `labs/lab8/cloud/producer.py`.

## What we discuss in class

**Event time against processing time.** The windows use event time (`modifiedDate`), so a payment
counts in the minute it happened, however late we hear of it, and a replay gives the same answer as
live. A late event is counted while its window is open; after the 2 minutes of grace it is rejected
and counted as rejected, never added to a window already reported.

**Why the same raw data is kept twice, as JSON and as Parquet.** JSON is the record of what really
arrived: nothing is interpreted, so a bug in the deduplication or a new question can be answered by
rebuilding from it. Parquet is a product made from it for reading: 120 times cheaper per query, but
already deduplicated, so anything that step threw away (here the first two events of every payment)
can come back only from the JSON.

**When a nightly batch is enough and when the business needs seconds.** Ask what changes if the
answer is an hour late. Turnover, reports and model training: nothing, so a nightly batch does it,
and it is complete because late events have arrived by then. Surge, fraud and a payment provider
going down: the decision expires within minutes, so the stream pays for itself. Note the price of
speed in Part 2 and Part 3: the batch answer is exact, and the stream's depends on how long it waits.

**What a managed service gives over running Kafka and Spark yourself, and what it costs.** It gives
no brokers to patch, no disks to size, scaling and failover by someone else, and a bill that starts
small. It costs more per unit at high steady volume, ties the design to one provider's limits and
API, and hides the knobs when something misbehaves. A team without people on call for Kafka should
pay; at Uklon's volume the sum is worth doing again.
