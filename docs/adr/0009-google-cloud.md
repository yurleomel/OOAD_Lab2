# ADR 0009 — A second deployment of Lanora's core on Google Cloud

- **Status:** accepted, 2026-11-17; core deployment and database read verified, then SQL stopped.
- **Context:** Lab 9. Target project `lanora-511019`, region `us-central1`.

## Context

Lanora currently serves its static Next.js frontend through S3/CloudFront and its FastAPI API
through Lambda. The actual database is **RDS PostgreSQL 17.6, db.t4g.micro, 20 GB gp2** in
`us-east-1`, not the pausing Aurora instance in the course's reference cost table. Cognito,
the report and agenda parser are managed by the `peach-prod` HCP Terraform workspace.

The lab requires a usable frontend, API and database on GCP, a service mapping for the wider
system, and a cost comparison. It does not require rewriting authentication or moving all
asynchronous features. Existing AWS infrastructure and data must remain intact.

## Decision

Deploy a second, independent SQL-backed core. Use an additive SQL baseline of the current
Alembic revision 0005 against an empty GCP database. Historical upgrades 0002/0003 contain
removals, so the GCP initialization job does not replay them. Compare the baseline with the
ORM using `alembic check`; later migration heads require explicit review of this job.
Signing in with the same Cognito subject creates a user in that database;
tasks are not synchronized with AWS. Preserve the database schema, user scoping and API
contract, and use a separate standard HTTP container for Cloud Run.

| Existing component | GCP counterpart | Decision for this deployment |
|---|---|---|
| S3 + CloudFront frontend | Firebase Hosting | Replace hosting for the second site; retain AWS site |
| Lambda + function URL + API CloudFront | Cloud Run HTTPS service | Replace runtime; same FastAPI routes, no Lambda handler |
| ECR | Artifact Registry | Build a Linux amd64 image with an immutable digest |
| RDS PostgreSQL db.t4g.micro | Cloud SQL PostgreSQL db-f1-micro, 10 GB SSD | Use SQL and migrations; stop compute between demonstrations |
| DynamoDB (not used) | Firestore | Do not introduce it: it would require rewriting relations and queries |
| Cognito + Google provider | Identity Platform/Firebase Auth | Keep Cognito; initially use email/password on the GCP site |
| EventBridge Scheduler | Cloud Scheduler | Keep the weekly report schedule on AWS |
| SQS and DLQ | Pub/Sub or Cloud Tasks | Keep the AWS report pipeline; Cloud Tasks is closer to its work queue |
| S3 event → mailer Lambda | Cloud Storage + Eventarc → Cloud Run | Keep existing report delivery on AWS |
| SES | SES or an external mail provider | Keep SES; no new provider or API key. Existing mailer uses its IAM role |
| Bedrock agenda parser | Vertex AI/Gemini | Keep Bedrock in the product; compare Gemini separately in the lab demo |
| Secrets Manager / SSM | Secret Manager | Generate and store a separate GCP database URL; runtime accesses only this secret |
| CloudWatch | Cloud Logging | Cloud Run request/application logs are collected by GCP |
| AWS IAM roles | Service accounts + IAM | Separate deployer/runtime identities, no Owner/Editor for programs |
| Terraform aws provider, peach-prod state | google/google-beta providers, peach-gcp state | Separate root, remote state and OIDC trust |

### Database alternatives

- **Cloud SQL, always running:** least code change, predictable SQL semantics; compute bills
  even with no requests. The 24-hour comparison must include it.
- **Cloud SQL, stopped between demos — selected:** same code, lower compute usage; storage
  and backups still bill, start/stop is explicit and the app cannot read data while stopped.
- **Firestore:** no idle instance, but joins, foreign keys, migrations, the SQLAlchemy services
  and the data model must be replaced. Reads per list/dashboard request become a cost driver.
- **Keep RDS across clouds:** preserves one data set, but adds network latency, cross-cloud
  egress and access configuration; the current RDS instance is private. It also fails the
  selected lab path of moving the core database. No public RDS access will be added.

### Authentication and asynchronous features

FastAPI continues to verify Cognito ID tokens before any database access. Cloud Run's public
invoker permission permits the browser to reach it; it does not grant access to user data.
Production configuration disables local passwordless development sign-in.

The Firebase build can sign in with Cognito email/password without changing the app client.
Hosted login, Google and hosted logout additionally require adding Firebase origins to the
AWS app client's callback/logout allowlists. That is a later, separate AWS plan. The agenda
paste UI is hidden on GCP until the parser allows its new origin. The AWS report still reports
on AWS tasks; no claim is made that it reports on GCP tasks.

### Infrastructure and lifecycle

`gcp/bootstrap/` establishes the USD 5 alert, separate program identities, a workspace and
Workload Identity Federation using the immutable HCP workspace ID. Its state is local and
ignored. `gcp/` enables service APIs and owns hosting, registry, SQL, secret and Cloud Run.
Neither root owns AWS resources. Billing alerts notify; they do not cap spend.

The optional data-platform demonstrations add a separate `peach-dataflow` worker identity,
a private lab bucket and a US BigQuery dataset with two small tables. That worker can access
only the lab bucket/dataset for data; no default compute identity or Editor role is used.
Terraform enables the demo APIs but does not launch any worker, model endpoint or pipeline.
One bounded batch job is launched separately for the three-row synthetic fixture.

HCP state contains the generated database credential even though plans redact it. Access to
state is restricted accordingly. Terraform resources prevent destruction; a plan guard also
rejects replacement. Start/stop changes use `database_running`; no deletion is part of this lab.

## Consequences

The core moves without changes to HTTP routes, SQL queries, migrations or user isolation.
Lock-in remains in PostgreSQL operations and the auth/event/AI services, rather than the
container runtime. Data does not synchronize and two environments have two operational bills.
This is an educational migration stage; operating a permanent split-cloud product would
need a deliberate data ownership and reporting design.

The main GCP cost trap is assuming that stopping Cloud SQL removes its bill: retained storage,
backups and idle public IPv4 remain chargeable. The IPv4 line alone is about USD 7.30 for
730 stopped hours at USD 0.01/hour. Raising Cloud Run minimum instances, enabling instance-based billing, an
unbounded Dataflow job or a large BigQuery scan can also change the bill. Demo results and
measured cost assumptions belong in [the lab report](../lab9.md), not invented here.
