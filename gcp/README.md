# Lanora on Google Cloud — Lab 9

Target project: **`lanora-511019`**. Region: **`us-central1`**. This is a second deployment of
the core, not a migration that shuts down AWS. Infrastructure has a separate HCP Terraform
workspace, **`peach-gcp`**, and a separate state. See [ADR 0009](../docs/adr/0009-google-cloud.md)
and the [submission checklist](../docs/lab9.md).

Verified on 2026-11-17: frontend **https://lanora-511019.web.app**, API
**https://peach-api-lwunl4a43q-uc.a.run.app**. Sign-in, a real database read and task persistence
passed before **Cloud SQL was stopped**. Database endpoints need the database started for a
new demonstration. Evidence and the remaining browser steps are tracked in the lab report.

Latest hand-in verification, 2026-11-17 20:34 Europe/Kyiv: a reviewed start plan applied
0 additions, 1 update and 0 deletions in HCP run `run-JuX3kqnv6XGRTZjk`.
Cloud SQL is now **RUNNABLE**, with `database_running = true`, for the lecturer's live check.
Authenticated readiness, list and the previously retained task read returned 200; anonymous
list access returned 401. The frontend deep route also returned 200. See
[`live-db-read-2026-11-17-submission.json`](../submission/lab9/live-db-read-2026-11-17-submission.json).
The exact hand-in text, cost table and calculator links are in
[`Moodle.txt`](../submission/lab9/Moodle.txt). Only that text and the three requested PNGs
belong in the concise submission. Stop instructions remain below; running SQL bills compute.

## Tools and authentication

Use Terraform 1.17+, Docker, Node and the pnpm version in `frontend/package.json`. The build
helper chooses Corepack so a globally installed pnpm 9 cannot misread the pnpm 10 lockfile.
The optional Firebase CLI is pinned to 15.36.0 and run through `npx` only when publishing;
the actual deployment here used the Hosting REST API with the existing gcloud login.

The Google Cloud CLI is available locally at `.gcp-builds/tools/google-cloud-sdk/bin/gcloud`
if the official portable SDK was downloaded during setup. Add that directory to this shell's
PATH, or install the official SDK separately. With the portable SDK on this Mac:

```bash
export PATH="$PWD/.gcp-builds/tools/google-cloud-sdk/bin:$PATH"
export CLOUDSDK_PYTHON=/opt/homebrew/bin/python3.13
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project lanora-511019
gcloud billing projects describe lanora-511019
```

The owner's browser completes Google sign-in/consent. No service-account JSON key is created,
downloaded or committed. CLI login and application-default login are separate: the former is
for `gcloud`, the latter for the one-time Terraform bootstrap. HCP runs use short-lived OIDC
credentials instead of either laptop credential.

If the CLI is already signed in but application-default credentials are absent, the helper
`python3 gcp/tf.py --bootstrap ...` obtains a short-lived access token from that CLI and passes
it only in the Terraform process environment (`GOOGLE_OAUTH_ACCESS_TOKEN`). It never prints
or saves the token. This avoids a second consent flow and is the bootstrap path used here.
The helper rejects delete/replacement plans before applying a saved bootstrap plan.

## One-time bootstrap, before any billable database

1. Confirm Billing is enabled for `lanora-511019` and obtain its billing account ID. Use
   `gcloud billing projects describe lanora-511019`; the billing account ID is not a card number.
2. Create `gcp/bootstrap/terraform.tfvars` from the adjacent example. Fill in that account ID,
   the project ID, and the existing public Cognito pool/client IDs from `.env`.
3. Initialize, plan, inspect the plan for deletions, then apply the reviewed plan:

```bash
terraform -chdir=gcp/bootstrap init
terraform -chdir=gcp/bootstrap plan -out=bootstrap.tfplan
terraform -chdir=gcp/bootstrap show -json bootstrap.tfplan | python3 gcp/check_plan.py
terraform -chdir=gcp/bootstrap apply bootstrap.tfplan
```

This sets a project-scoped **USD 5 monthly alert**, excluding credits, at 50%, 90% and 100%.
Billing administrators receive the default notifications. An alert is not a spending limit.
The bootstrap creates `peach-terraform` and `peach-api` identities; neither gets Owner or Editor.
The runtime can connect to Cloud SQL and read only its database secret. Terraform can act as
that one runtime identity, deploy the chosen services and manage their configuration.

The `peach-gcp` HCP workspace uses remote execution and manual approval. Its OIDC trust is
restricted to the immutable workspace ID. `gcp/bootstrap/` has local state, which must be kept
safe and is ignored by Git and HCP uploads. It owns IAM, federation and the budget; `gcp/` owns
the application resources. These roots do not manage the same resource.

## Prepare the infrastructure and build the API

```bash
terraform -chdir=gcp init
terraform -chdir=gcp plan
```

Review and apply in HCP Terraform. The first apply leaves `api_image = null` and
`database_running = true`: it creates the registry, secret, running Cloud SQL instance and
Firebase site. The instance must be running to provision its database/user and initialize it.
**Cloud SQL charges compute while running, and storage/backup storage even while stopped.** Do not treat
this first apply as free. No hello-world image is published under the API's URL.

If Firebase was already enabled or the default Hosting site already exists, import that
resource into the new state before the first apply; do not recreate it. The IDs are
`projects/lanora-511019` for `google_firebase_project.site` and
`projects/lanora-511019/sites/lanora-511019` for `google_firebase_hosting_site.site`.

```bash
python3 gcp/deploy.py build-image --project lanora-511019 --push
```

The build sends only `backend/` to Docker. The image runs Uvicorn on `$PORT` (8080 by default),
as UID 10001. The Lambda-specific base image, handler and adapter are not used. The shared
Python lockfile still includes `mangum`; it is an unused package in this image, preserving
the existing AWS dependency graph.

Set `api_image` in HCP to the printed **digest URL**, and set `database_running = true`.
Plan, review, then apply. Never set `api_image` back to null after deploying: that would request
deleting the service and migration job, and `prevent_destroy` rejects it.

Cloud Run has request-based billing, minimum 0 and maximum 1 instance, 1 vCPU, 512 MiB, and
concurrency 10. A Cloud SQL Auth Proxy Unix socket connects it to PostgreSQL; no authorized IP
networks are added. `DATABASE_URL` is read from a numbered Secret Manager version. Its password
is generated by Terraform and is never an output. It is still present in encrypted HCP state,
so access to state is access to the secret.

## Migrate, publish and verify

The chosen approach is an **additive SQL baseline of revision 0005 into a new empty database**,
not exporting AWS user data. Historical migration 0002 removes a column and 0003 clears old
items, so they are never executed by this job. `gcp/runtime/baseline.sql` creates the current
tables/indexes and records revision 0005. The initializer rejects an unexpected pre-existing
schema or a newer migration head, and preserves all rows on repeated runs. `alembic check`
verifies equivalence to the ORM without changing the schema. Run initialization outside API startup:

```bash
gcloud run jobs execute peach-migrate --project lanora-511019 --region us-central1 --wait
terraform -chdir=gcp output -raw api_url
```

Use that real API URL for the frontend build:

```bash
python3 gcp/deploy.py build-frontend --project lanora-511019 --api-url https://THE-REAL-CLOUD-RUN-URL
```

The script copies tracked frontend source into a **new** `.gcp-builds/frontend-…/` directory,
installs the frozen lockfile and builds there. Existing `frontend/out`, `.next`, dependencies
and prior artifacts are retained. It prints the exact publication command. A build made with
the validation-only placeholder URL is not a deployable submission artifact.

Add `--rest` to the printed publication command to use Firebase's Hosting REST API with the
already authorized gcloud identity, avoiding a separate Firebase CLI login. The short-lived
token stays in memory; uploaded content is deterministically gzipped and hashed. A new version
is finalized and released, and earlier versions are retained. Publication refuses an artifact
whose API URL differs from the deployed Terraform output.

Firebase serves the exported HTML using clean URLs, including `/items/list` and
`/auth/callback`. It does not rewrite missing routes to the sign-in page. Hashed assets are
immutable. Cloud Run accepts CORS requests only from the two Firebase default origins.

Sign in with the existing **Cognito email/password** on `https://lanora-511019.web.app`.
Google is hidden on this first GCP build: its OAuth callback and hosted logout URLs must be
added to the existing AWS Cognito configuration in a separate, additive AWS plan before it
is enabled. The GCP build disables hosted redirects and signs out locally, avoiding a hosted
logout redirect to an origin that is not yet registered. Existing AWS builds retain hosted
sign-in/logout by default. The AWS agenda parser remains available on the AWS site; the GCP build hides the
paste integration until its new origin is also allowed in that parser's CORS configuration.
The scheduled AWS report reads the AWS database, not this independent GCP database.

Check in a private window:

1. Frontend and deep routes load, including a refresh of `/items/list`.
2. Email/password sign-in succeeds; Network shows the **GCP** API, not `api.mylanora.world`.
3. `GET /api/v1/items` and `GET /api/v1/health/ready` return 200 with a valid token.
4. A task created in GCP persists after refresh. Preserve this task as demo evidence.
5. Calling `/api/v1/items` without a token returns 401; `/local/sign-in` is unavailable.

Capture actual outputs and screenshots in `submission/lab9/`. Do not place bearer tokens,
database URLs, personal account data or local auth files in the submission.

## Stop compute after the demonstration

Set `database_running = false` in the **GCP** workspace, review the update-only plan and apply.
This stops Cloud SQL compute without removing data. The public API will remain healthy at
`/health`, but database endpoints are unavailable until the database is started again.
Cloud Run scales to zero on its own. Storage, backups and other retained resources can still
bill; inspect Billing Reports the next day. No destroy, cleanup or deletion target is provided.

Use the guarded helper for the current HCP workspace inputs and a uniquely named saved plan:

```bash
python3 gcp/hcp.py database_running false
python3 gcp/tf.py plan -out=stop-reviewed-UNIQUE.tfplan
# Inspect the update-only plan before applying it.
python3 gcp/tf.py apply stop-reviewed-UNIQUE.tfplan
gcloud sql instances describe peach-postgres --project lanora-511019 \
  --format='json(name,state,settings.activationPolicy)'
```

For a later live demonstration, set the input to `true`, create/review a new start plan and
apply it, then check authenticated readiness. Stop it again afterwards using a new plan.
Do not execute initialization again just to start the existing database.

**IPv4 is another retained cost:** this small lab uses the public-IP Cloud SQL Auth Proxy
connection path, with no authorized client networks. Cloud SQL's pricing lists idle IPv4
addresses at USD 0.01/hour, and its stop documentation says IP/storage charges continue.
Include that line when estimating a stopped instance: 730 idle hours can add about USD 7.30,
in addition to 10 GB SSD and backups. Stopping compute alone must not be described as zero cost
or as storage-only. No address, instance or stored data is removed automatically.

## Bounded Part 4 demos

The bootstrap creates a third identity, `peach-dataflow`, scoped to the lab bucket/dataset.
The main root creates `lanora-511019-lab9` and the US dataset `lab9`. APIs are enabled in
Terraform; applying infrastructure does not start Dataflow or invoke a model.

```bash
python3 gcp/demos.py bigquery
python3 gcp/demos.py ocr
python3 -u gcp/dataflow_demo.py
python3 gcp/gemini_demo.py
```

Run each paid demo deliberately once. BigQuery uses a dry run and 100 MiB maximum, and writes
only to its initially empty table; it refuses to overwrite a populated result. OCR requires
Pillow and sends one generated synthetic receipt. Dataflow uploads three small fixtures with
`--no-clobber`, writes to a unique output table, uses at most one worker and requests cancellation
after 12 minutes. On completion it checks the three rows and 30-minute total. If interrupted,
inspect the saved `dataflow-launch-*.json` job ID and stop any remaining worker job; preserve
its files/output. Gemini makes one capped call with the actual Lab 6 prompt, validates the
response using the application schema and does not retry a paid response automatically.

Results are new JSON files in `submission/lab9/`; local containers and artifacts are retained.
These CLI results do not substitute for the required Looker Studio chart, OCR screenshot or
Vertex AI Studio UI step. See the lab report for actual job IDs/results and what is pending.

## Local checks

```bash
terraform fmt -check -recursive gcp
terraform -chdir=gcp init -backend=false -input=false -lockfile=readonly
terraform -chdir=gcp validate
terraform -chdir=gcp/bootstrap init -backend=false -input=false -lockfile=readonly
terraform -chdir=gcp/bootstrap validate
python3 -m unittest discover -s gcp -p 'test_*.py'
docker build --platform linux/amd64 -f gcp/Dockerfile --build-context cloud-runtime=gcp/runtime -t peach-gcp:lab9 backend
```

Offline validation checks provider schemas and references; it does not prove permissions,
available billing or a working deployment. Real plans must contain **zero delete actions**,
including replacement. `gcp/check_plan.py` rejects these in a `terraform show -json` document;
also inspect the HCP plan before approving it. Resources have `prevent_destroy` in addition.

## References

- [Cloud SQL connections from Cloud Run](https://cloud.google.com/sql/docs/postgres/connect-run)
- [HCP Terraform dynamic GCP credentials](https://developer.hashicorp.com/terraform/cloud-docs/dynamic-provider-credentials/gcp-configuration)
- [Firebase Hosting configuration](https://firebase.google.com/docs/hosting/full-config)
