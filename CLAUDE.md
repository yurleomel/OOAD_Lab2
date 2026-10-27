# Peach — notes for agents

Read `PROJECT.md` first: it is the specification, and code is generated from it. `README.md` is the
upstream course document, kept as reference. Items marked ★ in `PROJECT.md` were missing from the
upstream repository and are being written here.

## Status of the ★ items

| Area | State |
|---|---|
| Backend: auth, users, `/me`, migration `0003`, local sign-in, tests | done — `pytest` 46 passed |
| Frontend: `lib/auth.ts`, sign-in pages, `AuthGate`, `task-dashboard`, List view, ClickUp-style redesign | done — vitest 57 passed, static export builds |
| Local run: `docker compose up --build` with local sign-in (no AWS) | done — verified in a browser: sign in, add, reload, per-user isolation |
| Cognito: `infra/auth.tf` (until Lab 7 `cognito.yaml` + `deploy-cognito.sh`) | deployed (pool `us-east-1_qEVU77JkT`, Essentials tier, managed login v2 + default branding, logout URLs) |
| Lab 4: `/login` opens Cognito's managed login (password + Google) via oidc-client-ts; header Sign in on signed-out pages; log out goes through the domain's `/logout` | done - Google enabled (In production), both sign-ins checked on app.mylanora.world. The hosted flow needs `NEXT_PUBLIC_COGNITO_USER_POOL_ID` (repo variable `COGNITO_USER_POOL_ID` for CI) |
| AWS: backend on Lambda + RDS PostgreSQL, site on S3 + CloudFront | live - site https://app.mylanora.world, API https://api.mylanora.world (behind them d6qjoq19m7ta0.cloudfront.net and the function URL ama23qrervq2gu4uepqxl7jcce0stitq.lambda-url.us-east-1.on.aws); Cognito sign-in checked end to end on both |
| API domain: `api-edge.yaml`, `domain-backend.sh` | not started |
| CI: `ci.yml` - ruff, pytest on Postgres, eslint/prettier/tsc, vitest | done |
| CD: `deploy.yml`, OIDC role `peach-github-deploy` (trusts this repo's `main` only), repo variables | done - every push to `main` checks, then ships the backend (image tagged with the SHA) and the site |
| Lab 5 weekly report: `app/reports/` (report, builder, mailer), `items.completed_at` (0004), `infra/reports.tf` (until Lab 7 `reports.yaml` + `deploy-reports.sh`), `report.sh`, `make report-*`; submission notes and answers in `docs/lab5.md` | done (`pytest` 82 passed) and live: Monday schedule, `make report-now`, mail through SES; since Lab 7 owned by Terraform |
| Lab 6 Paste an agenda: `app/ai/` (parser, Lambda handler, prices), agenda on tasks (`0005`), `infra/ai.tf` (until Lab 7 `ai.yml` + `deploy-ai.sh`; parser outside the VPC + $5 budget), `llm.sh`, `make llm-hello/parse/parse-logs`, the paste screen; ADR `docs/adr/0006-llm-agenda-parsing.md`, C4 `docs/architecture.md`, submission notes `docs/lab6.md` | done - `pytest` 124, vitest 72; `peach-ai` live (parser URL in `PARSER_URL`, $5 budget `peach-monthly`), prompt `agenda-v2`, Converse + Claude Haiku 4.5 (see gotcha); checked on app.mylanora.world: paste, pre-fill, correct, save |
| Custom domain for `app.` / `api.` (`api-edge.yaml`, `domain-backend.sh`) | done - `mylanora.world` at Namecheap, 4 CNAMEs by hand; HTTP redirects to HTTPS |
| Lab 7 Terraform: `infra/*.tf` (Cognito, report, parser), `infra/bootstrap/` (HCP OIDC role + workspace), `.terraformignore`, `make infra-*`, `scripts/infra-env.sh`, CI job `terraform`; ADR `docs/adr/0007-terraform.md`, submission notes `docs/lab7.md` | in progress - the three stacks deleted with every resource retained (27), bootstrap applied (workspace `peach-prod`, role `hcp-terraform-peach-prod`); next: import apply in HCP, "No changes" plan, VCS connection, a PR applied by a merge, the drift exercise |

## Running

```bash
docker compose up -d --build        # then http://localhost:3000 - sign in with any email
docker compose run --rm --no-deps backend sh -c "ruff check . && pytest -q"   # backend checks
docker compose run --rm --no-deps backend alembic check                         # models vs migrations
docker compose run --rm --no-deps frontend sh -c "pnpm lint && pnpm format:check && pnpm exec tsc --noEmit && pnpm test"
docker compose run --rm --no-deps -e NODE_ENV=production -e NEXT_OUTPUT=export frontend pnpm build
make infra-check                    # terraform fmt + validate, offline (CI's terraform job)
make infra-plan                     # remote plan in HCP Terraform (after terraform login, make infra-init)
```

## Gotchas

- Without `COGNITO_*` the app runs in local sign-in mode (`app/dev_auth.py`): any email, no
  password, tokens signed by the backend container. It is on only with `APP_ENV=development`, no
  pool, and not on Lambda; without it (e.g. `APP_ENV=production` and no pool) every `/api/v1`
  route answers `503`. After `make infra-env` rebuild both services to switch to Cognito.
- Backend tests need no Cognito: `tests/tokens.py` generates a key, hands its JWKS to the app via
  `COGNITO_JWKS`, and mints real signed tokens. Import it before `app.config` is first read.
- `docker compose exec backend …` only works while the backend is healthy; use
  `docker compose run --rm --no-deps backend …` when it is not.
- `frontend/AGENTS.md`: this Next.js version differs from training data — read its bundled docs
  before writing frontend code.
- `next build` inside the dev container needs `-e NODE_ENV=production`: the Compose override sets
  `NODE_ENV=development`, and Next then fails prerendering `/_global-error` with a null
  `useContext`.
- Frontend tests mock `next/navigation` globally (`tests/navigation.ts`, registered in
  `tests/setup.ts`); set `location.pathname` / `location.search` there and assert on `router`.
- `components/ui/*` stays as generated; restyle at the call site (see `inputClass` in
  `components/auth-layout.tsx`) or through the tokens in `app/globals.css`.
- The AWS account is on the **Free plan**: Aurora can only be created with "express configuration"
  (no CloudFormation property - hence RDS `db.t4g.micro`), and Route 53 cannot register domains
  (buy one elsewhere; Route 53 DNS zones and ACM do work).
- GitHub tokens for this repository carry an **immutable subject**
  (`repo:yurleomel@<id>/OOAD_Lab2@<id>:...`); `github-role.sh` reads the prefix from the GitHub
  API. CloudTrail's `AssumeRoleWithWebIdentity` events show the subject a failed run presented.
- Re-running `make github-role` is safe now; before the fix it deleted the stack's own OIDC
  provider ("web identity token could not be validated").
- `make deploy-backend` builds the image locally, so Docker must be running; `deploy-frontend.sh`
  builds with the pnpm pinned in `package.json` (via corepack if PATH has another major).
- Fresh DNS names can stay "not found" for up to an hour on resolvers that looked them up before
  the record existed (negative caching); `dig @1.1.1.1` shows the truth, and Playwright can be
  pointed past it with `--host-resolver-rules`.
- `.env` now carries the pool ids, so a rebuilt local stack signs in through Cognito; blank the
  `COGNITO_*` lines to get local sign-in back.
- The report functions and the parser run the **API's image** with another handler. Terraform
  reads it (and the VPC, security group, database URL) from the backend stack, so the backend
  stack comes first; Terraform ignores `image_uri` afterwards and `deploy-backend.sh` moves all
  three functions to every new image itself.
- `app/reports/mailer.py` reads `os.environ` directly and imports nothing from `app` on purpose:
  it runs outside the VPC, where the database code is useless. Everything else goes through
  `Settings`.
- SES starts in the **sandbox**: mail reaches verified addresses only. Each recipient is verified
  once by hand (`aws sesv2 create-email-identity --email-identity <address>`, a link arrives by
  email) and stays outside Terraform; the `mylanora.world` identity needs its three DKIM CNAMEs at
  Namecheap. Until they resolve, the sender is a verified address (`report_sender_address`).
- Bedrock on this account: Anthropic models need the **use-case form** (Bedrock -> Model catalog,
  filled by the account owner on 2026-10-20; `aws bedrock get-use-case-for-model-access` shows it) and, for the
  Claude 5.x models, a Marketplace agreement (`create-foundation-model-agreement`, done for Opus 5.5
  and Haiku 5.5). Claude 5.x still answered "not available for this account" on both APIs, so the
  parser runs `PARSER_API=converse` with `us.anthropic.claude-haiku-4-5-20251001-v1:0`; the lab's
  model is `parser_api = "messages"`, `parser_model = "anthropic.claude-opus-5-5"` in
  `infra/terraform.tfvars`.
- On bedrock-mantle a model id that the account cannot use comes back `404 does not exist` or `403
  not available`, never a hint about forms; check `aws bedrock get-foundation-model-availability`.
- `make parse` / `make llm-hello` run in the backend dev container with `~/.aws` mounted read-only.
- Namecheap switches the domain's DNS off (nameservers `failed-whois-verification.namecheap.com`)
  when the registrant email is not verified; both `app.` and `api.` then go dark. The owner clicks
  Namecheap's verification link; the records come back by themselves.
- Remotes: `origin` is the student repository, `upstream` is the course repository. Never push to
  `upstream`.
- **Terraform** (Lab 7): Cognito, the report and the parser live in `infra/*.tf`; the backend,
  frontend, API-edge and GitHub-role stacks stay CloudFormation and are read with
  `data "aws_cloudformation_stack"`. State and runs are in HCP Terraform (org `ooad-yurleomel`,
  workspace `peach-prod`, remote execution, dynamic AWS credentials through the role
  `hcp-terraform-peach-prod`). `terraform login` once, then `make infra-init`; `make infra-plan`
  plans remotely. There is no apply target: applies happen in HCP after a merge.
- `.terraformignore` at the repository root is load-bearing: with a working directory set, a CLI
  run uploads the whole repository, `.env` included, without it.
- `infra/bootstrap/` (OIDC provider, role, workspace and its env variables) has a **local state**
  on the owner's laptop and needs both AWS credentials and the `terraform login` token. Losing
  the state means re-importing its seven resources, nothing more.
- The workspace's sensitive Terraform variables (`google_client_secret`, `report_sender_address`,
  `report_recipients`, `budget_email`) are typed in the HCP UI by the owner, never committed.
  Without `budget_email` the plan wants to destroy the budget; a wrong address shows as a change
  to the mailer's environment.
- Import lessons that would come back on any re-import: the app client must not set
  `generate_secret` (it forces a replacement); the Google IdP needs every key Cognito computes in
  `provider_details` (`attributes_url`, `authorize_url`, `oidc_issuer`, `token_url`, ...) and
  `username = "sub"`; SQS needs `max_message_size = 1048576` set explicitly; the schedule `input`
  must match the stored JSON byte for byte. Sensitivity-only "update in-place" lines on import
  ("The value is unchanged") are not changes.
