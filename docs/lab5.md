# Lab 5 — a weekly report, built by events

What was built is described in `PROJECT.md` §12, "Weekly report". This file holds what the
submission asks for that is not code.

## Collecting the submission

| Item | How |
|---|---|
| 1. Commit | the merge commit of the `lab5-weekly-report` pull request (report code, `infra/reports.yaml`, both handlers) |
| 2. Email screenshot | `make report-now WEEK=<last week>`; the email arrives within a minute with `lanora-<week>.csv` attached |
| 3. Two reports in S3 | one from the schedule (`REPORTS_SCHEDULE="rate(5 minutes)" make deploy-reports`, wait, then `make deploy-reports` to go back to Mondays) and one from `make report-now`; then `make report-ls` (= `aws s3 ls s3://peach-reports-<account>/reports/ --recursive`) |
| 4. Three log lines | `make report-logs`: `trigger=schedule` and `trigger=sqs` from the builder, `trigger=s3` from the mailer |
| 5. Answers | below |

The dead-letter exercise: `REPORTS_FAIL_WEEK=2026-W30 make deploy-reports`, `make report-now
WEEK=2026-W30`, watch `make report-status` until the message reaches the DLQ (three attempts, each retried
only after the 6-minute visibility timeout, so about 20 minutes). Then `make deploy-reports` without it, and **Start DLQ
redrive** in the SQS console on `peach-report-requests-dlq`.

Same week twice: `make report-now WEEK=2026-W41` twice gives **two emails**. The builder is
idempotent — both runs write the same key, so S3 holds one file — but every write is a new
`ObjectCreated` event, and the mailer is not idempotent: it sends once per event.

## Answers (Part 3, Step 7)

**1. The mailer got the same `ObjectCreated` event twice. Where would you store "this report was
already sent", and what would the key be?**

In a DynamoDB table, written with a conditional put (`attribute_not_exists(pk)`) *before* the
email is sent; the put that fails means someone already sent it, and the function stops. A TTL of
a few weeks keeps the table small. Not in Postgres — the mailer is outside the VPC and cannot reach
it — and not as a tag or a second object in the bucket, because the mailer must not write where it
is triggered.

The key is the object's identity, not the week: `bucket/key#etag`, e.g.
`peach-reports-…/reports/2026-W40.csv#9b2cf535f27731c974343645a3985328`. A duplicate delivery of
one event has the same ETag and is dropped. Rebuilding a week with unchanged data produces the same
bytes, hence the same ETag, and is dropped too; a rebuilt report whose figures changed has a new
ETag and is sent again, which is what a reader would want. (With versioning on, the version id
works the same way.)

**2. The builder in the VPC could not reach SES. Three ways to fix it, with their monthly cost.**

| Option | Monthly cost (us-east-1) |
|---|---|
| NAT gateway | $0.045/h ≈ **$32.85**, plus $0.045 per GB processed and ≈ $3.65 for its public IPv4 address — about **$37** before any traffic. One AZ; two for availability doubles it |
| VPC interface endpoint for SES | $0.01/h per AZ ≈ **$7.30 per AZ** (two subnets ≈ $14.60), plus $0.01 per GB |
| The split built here: mailer outside the VPC, joined by an S3 event | **$0** fixed: the S3 gateway endpoint is free, a few Lambda invocations and S3 notifications are inside the free tier |

With ten more emails a week: the split. Anything with an hourly price costs more in a month than
the emails do in years. With a million: SES itself is then the bill — $0.10 per thousand, about
$100 a week, ~$430 a month — and the endpoint or NAT is a rounding error next to it; the split
still costs nothing extra and scales with Lambda. I would keep the split and batch recipients (SES
takes up to 50 per message) and move off the sandbox; a NAT gateway only earns its price if many
things in the VPC need the internet, not just email.

**3. A presigned URL dies with the Lambda role's temporary credentials. How would you send a link
that works for a week?**

Do not sign the link when the email is sent; sign it when it is clicked. The email links to the
app — `https://app.mylanora.world/reports/2026-W40` — and the API, after the usual sign-in, answers
with a presigned URL valid for a few minutes, signed with the API function's current credentials.
Generating a presigned URL needs no network call, so it works from the VPC with no NAT; the
download itself goes from the browser straight to S3. The link in the email never expires, and
access is controlled by who can sign in, not by who has the email.

The alternatives: CloudFront in front of the bucket with CloudFront signed URLs (signed with a key
pair, any expiry, no IAM credentials involved), or signing with a dedicated IAM user's long-term
access key kept in Secrets Manager — SigV4 caps that at seven days, exactly the requirement, but it
means a long-lived key to rotate.
