# Lab 7 — The cloud as code: from CloudFormation to Terraform

What was built is in `infra/*.tf`, `PROJECT.md` §12 and §14 ("HCP Terraform"), and
[ADR 0007](adr/0007-terraform.md). This file holds what the submission asks for that is not code,
the migration log, and the answers to Step 7 and the class questions.

## Collecting the submission

| Item | How |
|---|---|
| 1. Commit | [PR #12](https://github.com/yurleomel/OOAD_Lab2/pull/12), merged as `7006dcf`: `infra/versions.tf`, `variables.tf`, `stacks.tf`, `auth.tf`, `reports.tf`, `ai.tf`, `outputs.tf`, `terraform.tfvars`; `cognito.yaml`, `reports.yaml`, `ai.yml` and their deploy/destroy scripts deleted; `Makefile` (`infra-*`, no apply), `README.md` §11, ADR 0007 |
| 2. Apply finished | run `run-5PM8AEjzcAoSdkVx`, started by merging [PR #13](https://github.com/yurleomel/OOAD_Lab2/pull/13) (report log retention 7 → 14 days): from GitHub, branch `main`, commit `96cda7b`, trigger "File change detected in tracked directory", execution mode Remote; **Apply finished: 0 added, 2 changed, 0 destroyed**. The pull request's check showed the same plan first (`run-4aaLg5hV1FZTSCLQ`, "0 to add, 2 to change, 0 to destroy") |
| 3. No changes | `make infra-plan` right after the import apply, below |

## Migration log

| | `peach-cognito` | `peach-reports` | `peach-ai` | Total |
|---|---|---|---|---|
| CloudFormation resources (all got `DeletionPolicy` and `UpdateReplacePolicy: Retain`) | 5 | 15 | 7 | 27 |
| Terraform resources imported | 5 | 25 | 9 | **39** |
| Re-created | 0 | 0 | 0 | **0** |

27 became 39 because Terraform splits what CloudFormation keeps as properties: an inline role
policy is `aws_iam_role_policy`, a managed policy is `aws_iam_role_policy_attachment`, and the
bucket's public access block, ownership, encryption, lifecycle and notification are five resources
of their own. Every one was imported, the child resources too: the lab allowed re-creating the
bucket notification and the Lambda permissions, but between deleting the old permission and
creating the new one S3 could not invoke the mailer, and that week's email would be lost.

The order, with a check after each step:

1. The three templates got `Retain` on all 27 resources (commit "Retain every resource of the Lab
   4-6 stacks"), deployed as change sets that changed only the two policies. Before and after,
   the same: the three functions' environment (hashed), code, timeout and memory; the event source
   mapping `e7a68fef…`; 4 users in the pool; the app client; 4 reports in the bucket; 2 queues;
   the schedule; the parser URL; the budget.
2. `delete-stack` on all three: 27 × `DELETE_SKIPPED`. The same snapshot matched again, and the
   site, the API and the parser kept answering.
3. `infra/imports.tf`: 39 import blocks with the real IDs (pool id, `pool/client`, `pool:Google`,
   `role:policy`, `role/arn`, `default/schedule`, `function/sid`, `account:budget`, the queue URLs).
4. The plan, until it said nothing. What it caught on the way:
   - the app client with `generate_secret = false` **forced a replacement**: a new client id would
     have broken sign-in on the deployed site. The attribute is left unset, as in the template;
   - the Google IdP showed the keys Cognito computes itself (`authorize_url`, `token_url`,
     `oidc_issuer`, `attributes_url`, ...) and `username = "sub"`; they are written down;
   - SQS's `max_message_size` would have dropped from 1 MiB to the provider's 256 KiB default;
     it is set explicitly;
   - the schedule's `input` differed in whitespace only; it is the stored string, byte for byte;
   - four "update in-place" lines that only marked a value sensitive ("The value is unchanged").
5. Applied in HCP Terraform from a saved plan (run `run-fxkZgPzCAFUMrDr6`): `39 imported, 0 added,
   4 changed, 0 destroyed`. The four changes are the sensitivity marks on the Google secret, the
   builder's and the mailer's environment and the budget's subscribers. Before applying, the four
   workspace variables were compared with the live values by SHA-256 (a temporary output, never
   committed): identical, byte for byte. Each "change" finished in 0 s, and the live snapshot
   matched again afterwards. Then the plan below.
6. `imports.tf` and the three templates deleted from the repository, with the scripts that
   deployed them.

**Real drift found on the way.** The template said the mailer sends from
`reports@mylanora.world`; the live function had a verified gmail address, set by hand in the
console when the domain's DKIM records failed in Lab 5. A redeploy of the template would have
broken the mail again. The address is now `report_sender_address`, a sensitive workspace
variable, so the code and the cloud agree.

### `terraform plan` right after the migration

Full output: `submission/lab7/3-terraform-plan-no-changes.txt`. The run is
`run-E9mgd9TCwAqALdZD` in workspace `peach-prod`; the middle is 39 refresh lines.

```
$ make infra-plan
Running plan in HCP Terraform. Output will stream here. Pressing Ctrl-C
will stop streaming the logs, but will not stop the plan running remotely.

Preparing the remote plan...

The remote workspace is configured to work with configuration at
infra relative to the target repository.
...
Terraform v1.17.0
on linux_amd64

Initializing plugins and modules...
aws_cognito_user_pool.main: Refreshing state... [id=us-east-1_qEVU77JkT]
...
aws_lambda_permission.parser_url: Refreshing state... [id=peach-ai-ParserUrlPermission-TPpSVWgQXm3s]

No changes. Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your configuration
and found no differences, so no changes are needed.
```

## Two roads (Step 4)

GitHub Actions ships the application, HCP Terraform the infrastructure. The three functions that
run the API's image are on both roads, so they are split by attribute: Terraform owns everything
but `image_uri` (`ignore_changes`), and `deploy-backend.sh` moves them to each new image.

When a change needs both, for example a new environment variable that the parser reads:
**infrastructure first**. The Terraform pull request adds the variable, and the running (old) code
ignores it; then the application pull request ships the code that reads it. Removing goes the
other way: the code stops reading it, then Terraform removes it. Each half works with the other's
old version, so the order of the two merges can never break production.

## Drift (Step 5)

1. By hand, outside Terraform: the parser's timeout 30 → 45 s
   (`aws lambda update-function-configuration --function-name peach-agenda-parser --timeout 45`,
   the same call the console makes).
2. HCP Terraform, **New run → Plan only** (`run-E5GLgSuju7sd5sBX`): `0 to add, 1 to change,
   0 to destroy`, `aws_lambda_function.parser`, `~ timeout: 45 → 30`. The plan is the code's
   opinion: the refresh read 45 from AWS, the code says 30. (`make infra-plan` from the laptop
   showed the same, `run-nY3pMMZrdTMqzF2s`.)
3. **New run → Plan and apply** (`run-Er3zWbc7ozf4ncL9`): `0 added, 1 changed, 0 destroyed`; AWS
   reads 30 s again, and the next plan says "No changes".

Nothing announced the drift: it showed up only because a plan ran. With auto-apply, the next
merge that touched `infra/` would have reverted it just the same, as one line among others.

**If it had been a real 23:00 fix**, putting it back would undo the fix. The team should have
done the fix as a pull request (with auto-apply it reaches AWS in minutes, and the plan is the
review), or, if the console was truly faster, opened that pull request right after: the next
apply is when a hand fix dies. The fix would then live in `infra/ai.tf`, in Git, with an author
and a reason.

## Step 7 — Think it through

**How many imported, how many re-created?** 39 imported, 0 re-created (the log above).

**An attribute that replaces the user pool or the bucket.** `username_attributes = ["email"]` on
the pool, and `bucket` (the name) on the reports bucket; the pool's `name` too. Changing the first
destroys the pool with every account in it: everyone signs up again, under a new `sub`, so the
`users` rows (keyed by `sub`) and their tasks are orphaned; and the new pool and client ids break
the site's build and the API's token checks. Renaming the bucket would delete every report: AWS
refuses to delete a bucket with objects (no `force_destroy`), so the apply would fail halfway,
after the plan was already approved. Both now carry `lifecycle { prevent_destroy = true }`: a plan
that would replace them stops with an error instead of waiting for a careful reviewer.

**Where the Google client secret is now.**

| Place | Who can read it |
|---|---|
| Google Cloud Console, the OAuth client | owners of the Google project |
| Cognito, the Google IdP's `provider_details` | any AWS principal with `cognito-idp:DescribeIdentityProvider`, including the HCP role (AdministratorAccess) |
| HCP workspace variable, sensitive | nobody reads it back from the UI or API; but every run gets it, so whoever can make a run execute code (a merged pull request) could print it |
| Terraform state in HCP | in clear text; anyone with state access in the organization, and any laptop that ever ran `terraform state pull` |
| `.env` on the owner's laptop (`GOOGLE_CLIENT_SECRET`, from Lab 4) | that laptop; kept out of Git by `.gitignore` and out of HCP uploads by `.terraformignore` |
| plans and logs | not there: `(sensitive value)` |

The state and the laptop are the realistic leaks; the plan output is not.

**Two applies at the same moment with remote state.** HCP Terraform runs one run per workspace at
a time and locks the state for it; the second run queues, then plans against the state the first
one wrote. A workspace that follows a repository refuses CLI applies altogether. With a local
`terraform.tfstate` in Git there is no lock: both read the same old state and both apply, so
resources with fixed names fail on the second apply and resources with generated names are created
twice; then both commit their state, the merge conflict is in a JSON file, and whichever side
loses, its resources exist in AWS and in nobody's state.

**A narrower trust and the permissions the workspace needs.** Already narrowed in
`infra/bootstrap/main.tf`:

```
"app.terraform.io:aud": "aws.workload.identity"
"app.terraform.io:sub" like "organization:ooad-yurleomel:project:*:workspace:peach-prod:run_phase:*"
```

One step further would split the phases: `run_phase:plan` assumes a read-only role
(`TFC_AWS_PLAN_ROLE_ARN`), `run_phase:apply` the writing one (`TFC_AWS_APPLY_ROLE_ARN`), so a pull
request's plan cannot change anything. What the workspace really needs instead of
AdministratorAccess: `AmazonCognitoPowerUser` (the pool), `AWSLambda_FullAccess` (the three
functions, their URL and permissions), and IAM role actions (`iam:CreateRole`, `iam:PutRolePolicy`,
`iam:AttachRolePolicy`, `iam:PassRole`) limited to `arn:aws:iam::*:role/peach-*`; plus SQS,
Scheduler, S3 on the reports bucket, SES, Budgets, `ec2:*VpcEndpoint*`, CloudWatch Logs and
`cloudformation:DescribeStacks`. The IAM part is the one to fence (a permissions boundary): a
role that can create roles with any policy is an administrator by another name.

**Claude Code is asked to "add a staging environment".** It should produce one pull request:
the resource names derived from an `environment` variable (`peach-staging-*`) instead of
`project_name` alone; the backend and frontend stacks read per environment; a `staging` workspace
and its role in `infra/bootstrap/` (better, in a second AWS account); the non-secret values for
staging; the deploy workflow for staging; and the plan of both workspaces showing `0 to change`
for production. It should not, on its own: apply anything, production or bootstrap; create or
widen IAM roles and trust policies; set or read sensitive variables; touch production's state
(`import`, `state rm`, `state mv`); change the production workspace's settings (VCS, auto-apply);
change DNS; or merge its own pull request.

## What we discuss in class

### The need

**Artur's Lambda, found six months later.** Three options: import it (HCL plus an import block,
plan until clean: it becomes owned, reviewed and reproducible in staging); delete it; or leave it
and write it down as unmanaged. First find out whether anything uses it (CloudWatch invocations,
its triggers, CloudTrail). Used: import it. Not used: throttle it to zero for a couple of weeks
(reserved concurrency 0), then delete it. Leaving it is the option that recreates the problem.

**The 23:00 security group fix.** The next apply, triggered by any merge that touches `infra/`,
puts the old rule back: the fix is undone, and the plan shows it as one innocent "update in-place"
line. What makes it survive: the same change written as a pull request before the next apply (the
"break glass, then codify" rule), and drift detection that would show it anyway (a scheduled
plan, or HCP's health assessments). Better still, the fix goes through the pipeline at 23:00 too:
with auto-apply, a reviewed pull request is minutes.

### State

**CloudFormation keeps the state, Terraform makes you keep it.** Better with CloudFormation: there
is nothing to lose, lock, protect or bootstrap, and a failed update rolls back by itself. Better
with Terraform: one state spans providers (AWS, Google, GitHub, DNS), it can be read and edited
(`import`, `moved`, `state mv`), which is what made this migration possible without re-creating
anything, and every plan refreshes it, so drift shows up without asking.

**The state file deleted.** Lost: the map from each address in the code to the real resource id,
the cached attributes and the outputs. Not lost: the resources, which keep running, and the code.
Terraform now believes nothing exists, so the plan wants to create everything: names clash, or
duplicates appear. Recovery: HCP Terraform keeps every state version, so restore the previous one;
if that is gone too, import every resource again, which is exactly Step 3 (39 import blocks).

**Why not the state in Git.** First, secrets in clear text: here the database URL with its password,
the Google client secret and the email addresses, for everyone with read access, in every clone
and forever in the history. Second, no locking: two people apply from two copies, and the result
is a merge conflict in a JSON file and resources nobody owns. (Third: a forgotten `git pull` means
planning against an old state.)

### Workflow

**Harmless HCL, dangerous plan.** From this migration: `generate_secret = false` on the app client
looks like stating the default, and the plan said `# forces replacement`, a new client id and a
broken sign-in. Another: renaming `aws_s3_bucket.reports` to `aws_s3_bucket.report_bucket` is a
cosmetic rename in the diff and a destroy of the bucket in the plan (without a `moved` block).
Clearing `google_client_id` in `terraform.tfvars` is one line that destroys the Google IdP.

**`-target` and `state rm`.** `-target`: the security group must change now, but the rest of the
plan holds an unreviewed change or fails on a provider bug; apply only
`-target=aws_security_group.x`, then fix the rest normally. `state rm` (or a `removed` block with
`destroy = false`): a resource must leave Terraform without being deleted, for example the user
pool handed to another team's stack (this migration in reverse), or a resource deleted by hand
that the provider now fails to refresh.

**Agent writes, human reviews the plan, HCP applies.** Automate further: the agent also runs
`fmt`, `validate` and the plan, and reads the plan back, flagging every `forces replacement`, every
destroy of a stateful resource and every IAM change; policy checks (OPA or Sentinel) that refuse a
destroy of the pool, the bucket or the database; scheduled drift plans; cost estimates. Never: the
human approval of a plan that destroys or replaces data or changes IAM and trust, and the apply
credentials themselves (production, bootstrap) in the agent's hands.

### Architecture

**A white-label customer, prod · rozetka.** `infra/` becomes a module (`modules/peach`) whose
inputs are the customer: name prefix, domain, logo and colours (Cognito managed login branding),
Google client, mail domain. Each environment is a small root that calls it, `envs/prod`,
`envs/staging`, `envs/prod-rozetka`, each with its own HCP workspace, its own state and variables,
and its own OIDC role, trusted only by that workspace, in rozetka's AWS account (one bootstrap per
account). Changes: the new root and its variables, the bootstrap in the new account, DNS and
certificates for their domain, a Google OAuth client, the SES domain, and a deploy job for that
account. Stays the same: the module code, the application, its image and its tests, and the
pipeline's shape. A fix to the module reaches every customer through the same review.

**A run fails halfway through ten resources.** The world: the first N resources exist, the rest do
not. The state: Terraform writes each resource as it is created, so it holds those N (one that was
created but not finished is marked tainted and will be replaced). The code: unchanged, still all
ten. Next: read the error, fix the cause (a permission, a quota, a name already taken) in the code
or the account, and run again; the plan shows only what is missing. To undo instead, revert the
commit and apply: Terraform destroys the N it made. Never finish it by hand in the console.
