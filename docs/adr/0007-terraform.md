# ADR 0007 — The infrastructure of Labs 4–6 in Terraform, run by HCP Terraform

- **Status:** accepted, 2026-10-26
- **Context of:** Lab 7. Code in `infra/` (`auth.tf`, `reports.tf`, `ai.tf`) and `infra/bootstrap/`;
  how to run it in `README.md` §11, "Infrastructure as code".

## Context

Labs 4, 5 and 6 added three CloudFormation stacks: `peach-cognito` (the user pool, 5 resources),
`peach-reports` (the weekly report, 15) and `peach-ai` (the agenda parser and the budget, 7). Each
was deployed from a laptop by a script that gathered its parameters from other stacks, from the
live API function and from `.env`. That worked, with three weak spots:

- **Who changed what is not written down.** The scripts ran from one laptop, with one person's
  keys. The template said how a resource should look, the script decided which values it got,
  and nothing recorded which values were last used.
- **Hand fixes drift silently.** When the `mylanora.world` DKIM records failed, the mailer's
  `REPORT_SENDER` was switched by hand in the console to an address SES had verified. The
  template still says `reports@mylanora.world`; the next `make deploy-reports` would have broken
  the mail again. CloudFormation's drift detection found it only when asked (`DRIFTED`, 1 resource).
- **The project already reaches outside AWS.** The Google OAuth client, the GitHub repository and
  its variables, the DNS records at Namecheap. CloudFormation stops at the edge of the account.

A second environment is the next step for the course, and it needs one description plus variables,
not three scripts that read `.env`.

## Decision

1. **Terraform, one root module in `infra/`.** `auth.tf`, `reports.tf` and `ai.tf` replace
   `cognito.yaml`, `reports.yaml` and `ai.yml` resource for resource. The stacks that stay in
   CloudFormation (`backend.yaml`, `frontend.yaml`, the API domain and the GitHub role) are read,
   not rewritten: `data "aws_cloudformation_stack"` gives the API function, the database secret,
   the VPC and the site URL.
2. **Adopt, do not re-create.** Every resource was imported with an `import` block under the name
   it already had, including the role names CloudFormation generated, after `DeletionPolicy: Retain`
   and the deletion of the three stacks. The import plan was *39 to import, 0 to add, 0 to
   destroy*: the user pool kept every account, the bucket every report, the SES domain its DKIM
   tokens. Nothing was re-created.
3. **State and runs in HCP Terraform.** Organization `ooad-yurleomel`, workspace `peach-prod`,
   remote execution. The workspace follows `main` through the GitHub App: a pull request that
   touches `infra/*.tf` gets a plan as a check, the merge applies it (auto-apply). The Makefile has
   `infra-plan` and no apply.
4. **No AWS keys anywhere.** Each run gets an OIDC token from HCP Terraform and trades it for the
   role `hcp-terraform-peach-prod`. Its trust accepts only `workspace:peach-prod` of this
   organization, not every workspace. The role, its OIDC provider and the workspace itself are
   `infra/bootstrap/`, applied once from a laptop with the owner's credentials and a local state.
5. **Two roads, split by what they own.** GitHub Actions still ships the application: the image,
   the backend stack, the site, and the code of the three functions that run the API's image
   (`deploy-backend.sh` moves them to each new image). Terraform owns everything else about those
   functions and ignores `image_uri`, so neither road undoes the other.

## Alternatives

- **Stay with CloudFormation.** The state would be AWS's problem, not ours, and nothing would
  have to move. But it covers only AWS, a hand change stays invisible until someone runs drift
  detection, and a second environment means more parameter plumbing in shell.
- **AWS CDK.** Real code instead of YAML, but it compiles to CloudFormation and inherits the same
  boundary at the edge of AWS, and it brings a Node toolchain to the infrastructure.
- **OpenTofu.** The same language and the same files under an open licence. Chosen against only
  because HCP Terraform, which the course uses for state and runs, runs Terraform; the switch is a
  binary away if the licence starts to matter.
- **Terraform with an S3 backend, run by GitHub Actions.** One pipeline for everything, but the
  state bucket, its lock and the plan-on-PR wiring become ours to build and protect. HCP Terraform
  gives all three on its free tier.

## Consequences

- **Who can change the infrastructure:** anyone whose pull request to `main` is merged; the plan
  in the check is what gets reviewed. HCP Terraform applies with the workspace role. Owners of the
  HCP organization can also start runs and read the state. A laptop can plan
  (`make infra-plan`) but not apply: a VCS-connected workspace refuses CLI applies.
- **Where the secrets end up.** The Google client secret, the report sender and recipients and the
  budget email are sensitive workspace variables, write-only in the UI and `(sensitive value)` in
  every plan. They are also in the **state**, in clear inside it, as is the database URL the
  builder reads from Secrets Manager: the state is as secret as the database password. HCP
  Terraform encrypts it at rest and shows it only to people with state access. And they are where
  they always were: in Cognito, in the functions' environment, in the budget.
- **If HCP Terraform is down,** nothing that runs stops: the API, the parser and the report do not
  talk to it. Only infrastructure changes wait. In an emergency, change the resource in the
  console and write the same change into a pull request before the next run; if the outage lasts,
  `terraform state pull` (or a state download from the UI) moves the state to an S3 backend.
- **Ordering of the two roads.** A change that needs both goes infrastructure first, application
  second, and each half must work with the other's old version: a new environment variable is
  added by Terraform before the code that reads it ships, and removed only after the code stops
  reading it.
- **The bootstrap is the exception.** Its state is a local file on the owner's laptop. Losing it
  costs a re-import of its seven resources, not the infrastructure. A second environment adds one
  workspace and one role there.
