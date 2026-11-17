# Lab 9 — Lanora on Google Cloud

Assignment: https://learn.ucu.edu.ua/mod/assign/view.php?id=158424

Due: **2026-11-19, 23:55 Europe/Kyiv**. Target project: `lanora-511019`.

## Evidence status

This is the working report, not a completed submission. Do not mark a row done without its
real cloud output or screenshot.

| Requirement | Artifact | Status |
|---|---|---|
| Service choices, database/email trade-offs | `docs/adr/0009-google-cloud.md` | Accepted and deployed |
| Reproducible GCP infrastructure | `gcp/` and `gcp/bootstrap/` | Applied; independent HCP state |
| Commit/merged PR | [Lab branch history](https://github.com/yurleomel/OOAD_Lab2/commits/lab9-google-cloud) | Exact commit link supplied with the handoff |
| Budget, scoped service accounts, keyless HCP auth | GCP/HCP configuration and plan | Applied; remote plans authenticated with WIF |
| Frontend and authenticated API reading Cloud SQL | Firebase URL, private-window screenshot and `core-read-proof.json` | Passed; database now stopped |
| Four traffic profiles and calculator estimates | Cost table below | Pending calculator verification |
| BigQuery query and bytes processed | `bigquery-5d721cff.json` | Passed; clearer screenshot still needed |
| Looker Studio chart | `looker-studio-bigquery-chart.png` and `looker-studio.json` | Created and visually verified |
| Vision or Document AI OCR | `vision-ocr-dfdc251e.json` and synthetic receipt | API passed; screenshot pending |
| Dataflow small-file batch demo | `dataflow-verified-e2dbab92.json` | Completed; three output rows verified |
| Gemini agenda prompt in Vertex AI Studio | `gemini-agenda-a24ac7c3.json` and comparison below | Vertex API passed; Studio UI pending |
| Stop Cloud SQL and inspect billing | Update-only plan and later billing report | SQL stopped; next-day billing check pending |

## Deployment choices

See [ADR 0009](adr/0009-google-cloud.md) and [the runbook](../gcp/README.md). Use migrations
into an empty database via the reviewed additive revision-0005 baseline. Historical upgrades
that remove structures or data are not replayed. Do not copy private AWS user data. Keep sign-in and refresh on Cognito,
and leave the AWS report and parser in place. Initially the GCP frontend uses email/password,
with Google and agenda-paste hidden until their GCP origins are allowed by the AWS services.

Deployed frontend: **https://lanora-511019.web.app**. Cloud Run API:
**https://peach-api-lwunl4a43q-uc.a.run.app**. Cloud SQL is deliberately stopped after the
demonstration, so database-backed requests need `database_running = true` and a reviewed
update-only apply before another live demonstration. The frontend and API health route remain
reachable. A running database is not implied by the retained Firebase URL.

## Cost comparison to finish with the calculators

Compare **the actual project**, not the course's Aurora reference architecture. On 2026-11-17
the AWS database was checked read-only: RDS PostgreSQL 17.6, `db.t4g.micro`, 20 GB gp2,
Single-AZ, private, available, backup retention 1 day. It does not pause on idle.

Regions: AWS `us-east-1`, GCP `us-central1`. USD, on-demand, no tax, a 730-hour month.
Show list-price costs **before promotional credits**; record any free-tier benefits separately.
The existing AWS account's old/free-plan history must not be assumed to grant another free
year of RDS. GCP trial credit changes the amount payable, not the architectural comparison.

| Profile | Active hours | AWS core | GCP core, SQL left running | GCP core, SQL stopped outside profile |
|---|---:|---:|---:|---:|
| Nobody | 0 | $14.43 | $9.45 | $9.08 |
| Class demonstrations, 10 × 2 h | 20 | $14.43 | $9.46 | $9.11 |
| Office hours, 8 h × 22 days | 176 | $14.43 | $9.59 | $9.31 |
| Busy around the clock | 730 | $14.76 | $18.59 | $18.59 |

These are **calculated estimates**, reproduced by `python3 labs/lab9/costs.py`; calculator
screenshots are still pending. The busy profile is arithmetic only: no load generator runs.
Assumptions: 1 API request/second during active hours, 0.2 s billed duration, 0.5 GiB memory
on both APIs, 1 Cloud Run vCPU, no overlapping requests, 2 KiB responses to Europe. Assume the
monthly free allowances have not been consumed by other projects/functions on the billing
accounts. Promotional credits, tax, cold-start overhead and burst CPU credits are excluded.

AWS includes an always-running private RDS instance, 20 GB gp2, one $0.40 secret, 0.5 GB ECR,
3 MB S3 and 10,000 S3 GETs/month; CloudFront requests/transfer and logs stay within their shared
free quotas. AWS RDS prices were checked through the live AWS Price List API: instance SKU
`9HPEGXQTDDGH53C9` is $0.016/hour; storage SKU `G2TQUMAQNSQ7H65X` is $0.115/GB-month.

GCP includes 10 GB SSD at $0.17/GB-month, an assumed 1 GiB of backup data at $0.08/month,
Cloud SQL compute at $0.0105/hour when running, and idle public IPv4 at $0.01/hour when stopped.
Cloud Run's request-based free CPU/memory/request quotas are applied; egress to Europe is
estimated at $0.12/GiB without claiming the North America-only free outbound quota. One
registry image below 0.5 GB, one secret version, small logs and the Firebase site fit the
respective quotas. Source pages and calculator links are listed below.

Under these assumptions, GCP is cheaper for the first three profiles because of the smaller
database/storage line. AWS becomes cheaper in the busy profile because the assumed Cloud
Run CPU time exceeds its free quota while Lambda compute stays under its GB-second quota.
This is not a measured performance comparison or a claim that these small DBs sustain every
possible workload. Pausing a public-IP Cloud SQL instance saves little here: idle IPv4 nearly
replaces the tiny shared-core compute charge. Firestore would remove that instance/IP line,
but requires changing the relational model and counting document reads.

Fill calculator inputs explicitly: requests/second, average billed request duration, Lambda
memory, Cloud Run 1 vCPU/0.5 GiB/concurrency, outbound GB and database active hours. Active hours
alone do not determine API cost. Keep the actual AWS RDS always-running baseline, and label any
hypothetical stopped-RDS variant separately. Note that stopped RDS is automatically restarted
after seven days, unlike simply assuming an idle month has zero compute charges.

Required lines: frontend/CDN/HTTPS, API, database compute, storage/backups, registry, secrets,
logs, network egress; list excluded optional report/LLM workloads. Cloud SQL uses 10 GB SSD,
`db-f1-micro`; its storage/backups remain billable when stopped. Do not use the course's
rough USD 9.40 total as a verified estimate for this actual deployment.

Conclusions to fill after calculation: cheapest cloud for each profile; the single dominant
line; always-on Cloud SQL versus request-based Cloud Run; where replacing SQL with Firestore
would save spend but require query/model changes. Add the two calculators' saved estimates
or screenshots and the date they were checked.

Pricing sources:

- https://aws.amazon.com/rds/postgresql/pricing/
- https://cloud.google.com/sql/pricing
- https://cloud.google.com/run/pricing
- https://firebase.google.com/pricing
- https://calculator.aws/
- https://cloud.google.com/products/calculator

## BigQuery and Looker Studio

Use [the checked-in query](../labs/lab9/bigquery.sql). Dry run first:

```bash
bq --project_id=lanora-511019 query --use_legacy_sql=false --dry_run < labs/lab9/bigquery.sql
bq --project_id=lanora-511019 query --use_legacy_sql=false --maximum_bytes_billed=104857600 < labs/lab9/bigquery.sql
```

In the console, capture the SQL, real result and bytes processed. Save the result to a new
table in a dedicated US-location lab dataset, then connect Looker Studio to that table. Plot
`corpus` against `total_words` as a bar chart. Store a screenshot showing readable labels and
the data source. A BigQuery query alone is not evidence of a Looker chart.

BigQuery replaces the Athena query/warehouse portion of Lab 8; Cloud Storage replaces its
S3 landing files; Dataflow replaces Glue-style transforms; Looker Studio covers visualization.
No cluster is provisioned for BigQuery, but scans still cost money beyond the quota. Setting
`LIMIT` does not reduce bytes read from all scanned columns.

The actual Looker Studio report is
[Lab 9 — Shakespeare words from BigQuery](https://datastudio.google.com/reporting/49eadb28-85bc-4337-a81b-4f262abd613d/page/TymDG).
It connects directly to the saved `shakespeare_top10` table and shows ten horizontal bars:
`corpus` on Y, `SUM(total_words)` on X, descending. Hamlet has 32,446 words and Antony and
Cleopatra has 27,310, matching the saved query result. The report remains private to its owner;
the submission contains the readable screenshot, source table and field configuration.
The current Google UI labels the product **Data Studio / Центр даних** and displays a banner
explaining the rename from Looker Studio; this is the same service requested in the lab.

## Other Part 4 demonstrations

- **OCR:** choose Vision text detection on a receipt/handwritten photo OR Document AI OCR on
  one PDF. Use a synthetic document without personal details. Save the actual input/result
  screenshot and list the processor/API used. These are alternatives for the required OCR
  submission screenshot; both are not needed.
- **Dataflow:** use the Google-provided Cloud Storage Text to BigQuery batch template and a
  tiny synthetic file, dedicated bucket/output table, one worker and the chosen region. Check
  its schema/UDF requirements before launching. Wait for completion and verify the rows.
  Do not start a perpetual streaming job for this demo.
- **Vertex AI Studio:** run the actual agenda prompt/test input from Lab 6 using an available
  Gemini model. Record the exact model/version, recognized fields, output validity, token
  usage and cost; compare it with the saved Bedrock answer. Partner models may not be covered
  by the trial credit.
- **In-class only:** Veo, enterprise Looker and managed Airflow. No student deployment is
  required. Certification is a separate optional bonus, not a required lab deliverable.

Document AI is useful for document layout, tables and repeated extraction schemas; the LLM
is useful for the semantic interpretation of the pasted agenda. An OCR result does not by
itself supply the meeting's owners, durations or action items.

### Actual one-off results, 2026-11-17

- **BigQuery:** job `lab9_words_989592b8da894837867ed2de890465a3`, location US; public
  Shakespeare query processed **3,781,873 bytes** (3.61 MiB) and billed 10 MiB before applying
  the monthly free allowance. Dry run and execution both used a 100 MiB ceiling. Ten rows were
  written with `WRITE_EMPTY` into `lanora-511019.lab9.shakespeare_top10`. No existing table
  content was overwritten. The current console screenshot needs recapturing: its narrow
  layout cuts off the byte statistics and the editor warns that the destination is already
  populated. The saved successful job JSON contains the actual statistics and result.
- **Vision:** one `TEXT_DETECTION` call recognized the synthetic receipt, including
  `LANORA TEST CAFE` and `TOTAL 3.50`. Input: `synthetic-receipt-ea77eb7d.png`; full actual
  result: `vision-ocr-dfdc251e.json`. No real receipt or personal document was uploaded.
- **Dataflow:** Google `GCS_Text_to_BigQuery` classic batch template, job
  `2026-11-17_05_01_10-8688510766657573056`, ran from 13:01:12 to 13:05:07 UTC and reached
  **JOB_STATE_DONE**. Configuration: one `e2-standard-2`, maximum one worker, 30 GB disk,
  dedicated worker identity, three CSV rows, unique output table
  `lanora-511019.lab9.dataflow_demo_a714f4b8abd5`. A direct table-data read verified IDs 1–3,
  their topics and 30 total minutes. A subsequent Compute inventory returned no instances.
  The template's temporary files and output are retained.
- **Gemini:** one Vertex AI API request to `gemini-3.8-flash`, global endpoint, low thinking,
  maximum 1,024 output tokens. It used the original `agenda-v2` system prompt/tool schema,
  Lab 6 Ukrainian input 1 and reference date 2026-10-20. The response invoked `record_agenda`
  once and passed the original `ParsedAgenda` Pydantic validation. This API call is useful
  evidence but does not complete the requested Vertex AI Studio UI step.

| Same Lab 6 input 1, `agenda-v2` | Correct fields | Invented values | Input / output tokens | Estimated call cost |
|---|---:|---:|---:|---:|
| Saved Bedrock Claude Haiku 4.5 result from Lab 6 | 15 / 15 | 0 | 1,754 / 287 | $0.00319 |
| Actual Vertex Gemini 3.8 Flash response | 15 / 15 | 0 | 798 / 173 | $0.002495 before promotional credits |

Both answers preserve the 10:00 wall-clock start on 2026-10-26, 45-minute duration, three
topics, empty unspecified owners/minutes and the action due 2026-10-23. This is one fixture,
not a general accuracy ranking; each provider also tokenizes the same text differently. No
new Bedrock request was needed for the comparison. Gemini pricing checked on 2026-11-17:
standard global $1.50 / $7.50 per million input / output tokens, with introductory effective
$0.75 / $3.75 through 2026-12-31 via credits back. Thus the effective introductory estimate is
$0.00124725; the table uses the conservative pre-credit price. Actual billing can arrive later.
Source: [Google model pricing](https://cloud.google.com/model-garden/pricing).

## Submission

Submit the actual commit/merged PR, the Firebase site URL with a demonstrated database read,
the completed cost table with free-tier assumptions, and the three screenshots (BigQuery,
Looker Studio, one OCR service). Store evidence under `submission/lab9/` only after it exists.
Preserve all data and artifacts; stop database compute after the demonstration and check
Billing Reports the next day.

## Verified deployment and stop (2026-11-17)

- Bootstrap plans applied 31 and then 5 additions; core plans applied 17 and then 15 additions.
  All four plans had **zero delete actions**. The second bootstrap added the dedicated
  Dataflow identity and scoped demo permissions. There are separate API, Terraform and
  Dataflow identities; no service-account key was downloaded.
- HCP `peach-gcp` deployed the API image by digest and initialized the new database with job
  execution `peach-migrate-q5qgt`. The additive revision-0005 baseline and `alembic check`
  succeeded.
- An isolated, synthetic Cognito account authenticated against the real API. Database
  readiness, task creation, list and fetch-by-ID succeeded; the task persisted. Anonymous
  access returned 401. The account and task are retained; credentials are private local
  artifacts and are not in this report.
- A private Chrome window loaded the Firebase site, signed in, displayed the task board and
  kept the task after refresh. `gcp-board-private-window.png` records the actual page.
- Firebase release `sites/lanora-511019/releases/1794919399614000` uses the real GCP API URL.
  HTML revalidates on each request; hashed static assets are immutable. Previous releases
  and build directories were preserved.
- `stop-db-01.tfplan` applied **0 additions, 1 update, 0 deletions**, setting
  `database_running = false`. A subsequent API description returned SQL **STOPPED** and
  activation policy **NEVER**. Dataflow completed and its workers are no longer present.
  SQL disk, backups and idle public IPv4 remain chargeable; the USD 5 alert is not a cap.
- Still required: readable BigQuery and OCR screenshots, the Studio UI
  step, official calculator evidence, and a billing check the next day.

### Continuation checkpoint (2026-11-17)

- Created the Looker Studio report and its BigQuery-backed chart. Saved and visually checked
  `submission/lab9/looker-studio-bigquery-chart.png` (3840 × 2028); its manifest records the
  exact source, fields and screenshot hash.
- Added `labs/lab9/cost_report.py` and `submission/lab9/cost-breakdown-2026-11-17.json`.
  Every profile now has individual service lines, inputs and totals. All component sums
  reconcile with `costs.py`. This is a forecast, not an invoice or a calculator screenshot.
- Rechecked the Google SQL/Run/Hosting/registry/secrets/logging and AWS Lambda/CloudFront
  pricing sources. Firebase **Hosting** has 10 GB storage and 360 MB/day transfer allowances;
  it is separate from Firebase App Hosting. The actual exported site is 91 files, 2.14 MiB
  uncompressed, and the GCP registry reported 83.899 MB. The cost model assumes static traffic
  remains below the daily transfer allowance, shared quotas remain available and AWS ECR
  retains 0.5 GB; those usage assumptions are not measured monthly bills.
- Added `submission/lab9/vision-ocr-evidence.html`, an explicitly labelled local viewer of the
  real Vision response beside its original synthetic image. Opening it makes no new OCR call.
  A browser screenshot of that page is still pending.
- Chrome became unavailable with `cgWindowNotFound` during the BigQuery screenshot step.
  Reconnecting the computer-use session did not restore a visible window. No SQL instance
  or Dataflow worker was started during this continuation. Remaining UI steps need access
  to the unlocked, visible browser.

### Earlier setup checkpoint (retained for provenance)

- `lanora-511019` is active and Billing is enabled; the unrelated Default Gemini project is untouched.
- Bootstrap applied **31 additions, 0 changes, 0 deletions**: USD 5 alert, two dedicated identities,
  project-scoped roles, HCP workspace `peach-gcp`, and OIDC trust/short-lived credentials.
- The first GCP core plan was **17 additions, 0 changes, 0 deletions**; its HCP plan authenticated
  through the new identity federation. Application-resource provisioning is in progress.
- Terraform root/bootstrap validation, plan-deletion guard tests, GCP Python lint, the Linux
  container build, and the static frontend validation build passed. Frontend auth checks: 18 passed.
- The local integration smoke used PostgreSQL 17 and a Unix socket: additive baseline and
  `alembic check` passed, authenticated readiness and task creation passed, repeat initialization
  preserved the task, user isolation passed, anonymous requests returned 401 and development
  sign-in returned 404. Its own containers were stopped and retained, and no test rows were deleted.
- Cost constraint: use tiny one-off demos; target under USD 1 for testing, excluding ongoing
  retained-resource costs. Cloud Run maximum is one instance and minimum is zero. No load test,
  Veo generation, managed Airflow environment or enterprise Looker deployment will be started.
- **Pricing correction to the reference:** idle Cloud SQL public IPv4 can cost USD 0.01/hour
  (about USD 7.30/month), in addition to storage when compute is stopped. Include this in the
  comparison instead of claiming a stopped public-IP instance costs only USD 1.70/month.
  Sources: https://cloud.google.com/sql/pricing and
  https://cloud.google.com/sql/docs/postgres/start-stop-restart-instance .
