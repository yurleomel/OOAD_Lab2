# Peach — PROJECT.md

This file is the specification of the repository: its structure, the contracts between its parts,
and how it runs locally and on AWS. It contains no implementation code. Code is generated from it
and reviewed against it; where the two disagree, this file wins until it is changed in a reviewed
commit.

`README.md` is the upstream course document and stays as reference. Items marked **★** below are
not in the upstream repository — they are referenced by upstream code but were never committed —
and are generated from this specification.

---

## 1. What Peach is

A personal task board. A person signs in, keeps tasks in three columns (To do, In progress, Done)
and sees their progress on a dashboard. Every task belongs to exactly one person; nobody sees
anyone else's tasks.

That is the whole product for this iteration. Section 16 lists what is deliberately left out.

---

## 2. Decision: one repository

Backend, frontend, database schema, infrastructure templates, deploy scripts and CI live in one
repository.

- **Atomic changes.** One commit changes an endpoint, its schema, its migration and the component
  that calls it, so the API and its client cannot drift apart.
- **The repository is the agent's context.** With the whole pipeline in one tree, an agent reads
  the route, the model, the migration and the React component in one pass. Split across three
  repositories, it sees a third of the system and guesses the rest — and a guessed contract is a
  bug found at integration time.
- **Cost we accept.** No independent versioning or access control per part, and CI runs for
  changes that only touch one side. For a team of four and a product that does not exist yet,
  context is worth more than that independence.
- **Boundary we keep anyway.** Nothing outside `backend/` imports Python from it; nothing outside
  `frontend/` imports TypeScript from it. The only contract between them is the HTTP API in §8.

---

## 3. Repository layout

```
Peach/
├── PROJECT.md                    # this specification
├── README.md                     # upstream course document (reference)
├── .env.example                  # every variable, with local defaults; committed
├── .gitignore
├── docker-compose.yml            # db, backend, frontend — production-shaped
├── docker-compose.override.yml   # dev only: bind mounts, hot reload (auto-loaded)
├── Makefile                      # the local and deploy contract (§13)
│
├── .github/workflows/
│   ├── ci.yml                    # ★ lint + tests on every PR and push to main (replaces lint.yml)
│   └── deploy.yml                # ★ on push to main: checks -> backend -> frontend (replaces deploy-backend.yml)
│
├── infra/                        # CloudFormation, one template per stack
│   ├── cognito.yaml              # ★ user pool, app client, hosted domain, optional Google IdP
│   ├── backend.yaml              # Lambda + function URL + Aurora Serverless v2
│   ├── api-edge.yaml             # ★ CloudFront in front of the function URL, for api.<domain>
│   ├── frontend.yaml             # private S3 bucket + CloudFront (+ app.<domain>)
│   └── github-oidc.yaml          # the role GitHub Actions assumes (extended: S3 + CloudFront)
│
├── scripts/                      # what the Makefile runs; CI runs the same scripts
│   ├── deploy-cognito.sh         # ★ deploy cognito.yaml, write COGNITO_* to .env
│   ├── destroy-cognito.sh        # ★ delete the pool and every account in it
│   ├── deploy-backend.sh         # build -> ECR -> CloudFormation -> migrate -> BACKEND_URL
│   ├── destroy-backend.sh
│   ├── domain-backend.sh         # ★ ACM cert + api-edge stack for api.<domain>
│   ├── deploy-frontend.sh        # static export -> S3 -> CloudFront invalidation
│   ├── domain-frontend.sh        # ACM cert + app.<domain> on the frontend distribution
│   ├── destroy-frontend.sh
│   └── github-role.sh            # create the OIDC role, set repository variables
│
├── backend/
│   ├── Dockerfile                # stages: builder, dev, runtime, lambda
│   ├── pyproject.toml, uv.lock   # dependencies; uv.lock pins every transitive version
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py               # app factory: CORS, /health, /api/v1 router
│   │   ├── config.py             # Settings from the environment; nothing else reads os.environ
│   │   ├── db.py                 # async engine, session dependency
│   │   ├── auth.py               # ★ Cognito ID-token verification, current_user, CurrentUser
│   │   ├── dev_auth.py           # ★ local sign-in for docker compose up without AWS (§9)
│   │   ├── lambda_handler.py     # Lambda entry: HTTP via Mangum, {"action":"migrate"} -> alembic
│   │   ├── models/               # ORM: item.py, user.py ★
│   │   ├── schemas/              # request/response models: item.py, user.py ★
│   │   ├── services/             # business logic: items.py, users.py ★
│   │   └── api/
│   │       ├── router.py         # /api/v1, every route behind current_user
│   │       └── routes/           # HTTP layer only: health.py, items.py, me.py ★
│   ├── migrations/versions/      # 0001, 0002, 0003_users ★
│   ├── scripts/entrypoint.sh     # migrate, then uvicorn (runtime image)
│   └── tests/                    # pytest against real Postgres; tokens.py ★, test_auth.py ★, test_me.py ★, test_local_sign_in.py ★
│
└── frontend/
    ├── Dockerfile                # stages: base, deps, dev, builder, runtime
    ├── package.json, pnpm-lock.yaml
    ├── next.config.ts            # output "standalone" (Compose) or "export" (S3)
    ├── app/
    │   ├── layout.tsx            # fonts, Providers, Toaster
    │   ├── globals.css           # theme tokens (§10 visual language)
    │   ├── page.tsx              # ★ / — sign in
    │   ├── signup/page.tsx       # ★ /signup — create account, confirm the emailed code
    │   ├── auth/callback/page.tsx# ★ /auth/callback — Google sign-in lands here
    │   ├── not-found.tsx         # ★ exported as 404.html
    │   └── (app)/                # signed-in area
    │       ├── layout.tsx        # ★ AuthGate + AppShell
    │       ├── home/page.tsx     # /home — dashboard
    │       ├── items/page.tsx    # /items — board
    │       └── items/list/page.tsx # ★ /items/list — the same tasks as a grouped list
    ├── components/
    │   ├── ui/                   # shadcn-generated; never hand-edited
    │   ├── app-shell.tsx         # ★ top bar, icon rail, sidebar with status counts
    │   ├── task-dialogs.tsx      # ★ one create/edit dialog + delete confirmation for every page
    │   ├── auth-gate.tsx         # ★ redirects signed-out visitors to /
    │   ├── auth-layout.tsx       # ★ backdrop + card shared by the signed-out pages
    │   ├── sign-in-form.tsx, sign-up-form.tsx, auth-callback.tsx, google-button.tsx  # ★
    │   ├── local-sign-in.tsx     # ★ the sign-in form of a build without a Cognito pool
    │   ├── task-dashboard.tsx    # ★ the /home dashboard
    │   ├── item-board.tsx, item-list.tsx ★, items-header.tsx ★  # the two views and their tabs
    │   ├── status-icon.tsx ★, brand-mark.tsx ★, item-form-dialog.tsx, page-header.tsx, providers.tsx
    ├── lib/
    │   ├── api.ts                # the only place that calls fetch; zod schemas mirroring §8
    │   ├── auth.ts               # ★ Cognito sign-in/up, token storage and refresh, useSession
    │   ├── use-items.ts          # ★ every task, paged through; the one ["items"] cache entry
    │   ├── item-status.ts        # status labels, icons and colours
    │   └── utils.ts
    └── tests/                    # vitest + Testing Library; next/navigation mocked in setup.ts
```

A folder that cannot be explained in one line does not belong here.

---

## 4. Pinned versions

| Piece | Version | Where it is pinned |
|---|---|---|
| Python | 3.14 | `python:3.14-slim`, `public.ecr.aws/lambda/python:3.14`, `requires-python` |
| uv | 0.12.21 | `ghcr.io/astral-sh/uv:0.12.21` in `backend/Dockerfile` (★ was `:latest`) |
| Python packages | exact | `backend/uv.lock`, installed with `--frozen` |
| Node | 22 | `node:22-alpine` |
| pnpm | 10.34.5 | `packageManager` in `package.json` |
| Next.js / React | 16.3.4 / 19.2.8 | `package.json`, locked in `pnpm-lock.yaml` |
| PostgreSQL (local) | 17 | `postgres:17-alpine` |
| PostgreSQL (AWS) | Aurora PostgreSQL 17.4 | `DbEngineVersion` in `infra/backend.yaml` |
| GitHub Actions | major tags | `actions/checkout@v4`, `aws-actions/configure-aws-credentials@v4`, … |

No `latest` anywhere an image or package is chosen.

---

## 5. Configuration

All configuration is environment variables. `.env.example` is committed; `.env` is git-ignored.
Access keys never enter the repository — not in `.env.example`, not in a workflow, not in a
commit meant to be amended.

| Variable | Read by | Local value | Set by |
|---|---|---|---|
| `POSTGRES_USER/PASSWORD/DB/PORT` | db | `peach` / `peach` / `peach` / `5432` | `.env` |
| `DATABASE_URL` | backend | `postgresql+asyncpg://peach:peach@db:5432/peach` | `.env`; on AWS the stack |
| `APP_ENV`, `LOG_LEVEL` | backend | `development`, `info` | `.env` |
| `CORS_ORIGINS` | backend | `http://localhost:3000` | `.env` |
| `DB_POOLING` | backend | `true` | `false` on Lambda (stack) |
| `NEXT_PUBLIC_API_URL` | frontend (browser, build time) | `http://localhost:8000` | `.env` |
| `INTERNAL_API_URL` | frontend (server) | `http://backend:8000` | `.env` |
| `AWS_REGION`, `PROJECT_NAME` | scripts | `us-east-1`, `peach` | `.env` |
| `AWS_PROFILE` | scripts | an IAM user's CLI profile | `aws configure` |
| `COGNITO_REGION/USER_POOL_ID/CLIENT_ID/DOMAIN/GOOGLE_ENABLED` | backend, frontend | — | `make deploy-cognito` |
| `GOOGLE_CLIENT_ID/SECRET` | deploy-cognito | blank = Google off | `.env`, by hand |
| `BACKEND_URL` | deploy-frontend | — | `make deploy-backend` / `make domain-backend` |
| `API_CORS_ORIGINS` | deploy-backend | `https://app.<domain>` | `.env`, by hand |
| `DOMAIN_NAME` | domain-frontend | `app.<domain>` | `make domain` |
| `API_DOMAIN_NAME` | ★ domain-backend, deploy-backend | `api.<domain>` | `make domain-backend` |

The browser and the frontend server use different API URLs on purpose: the browser resolves
`localhost`, a server component inside the Compose network resolves the `backend` service name.

---

## 6. Local stack

```bash
docker compose up --build
```

That is the only command a new developer runs; Docker Desktop is the only prerequisite. Every
variable has a default, so no `.env` is needed, and with no Cognito pool configured the app signs
in locally (§9): any email, no password, no AWS. `cp .env.example .env` is for overriding ports or,
later, for `make deploy-cognito` to write the pool ids into.

| Service | Built from | Host port → container | Depends on | Ready when |
|---|---|---|---|---|
| `db` | `postgres:17-alpine` | `5432 → 5432` | — | `pg_isready -U peach -d peach` succeeds (every 5 s, 10 retries) |
| `backend` | `backend/Dockerfile` | `8000 → 8000` | `db: service_healthy` | `curl -f /health` succeeds (every 5 s, 12 retries, 20 s grace) |
| `frontend` | `frontend/Dockerfile` | `3000 → 3000` | `backend: service_healthy` | — (last in the chain) |

**Startup order is enforced, not assumed.** `depends_on` alone only orders container start; the
`condition: service_healthy` form makes the backend wait until Postgres answers, and the frontend
until the API answers. The backend applies migrations (`alembic upgrade head`) at container start,
before Uvicorn listens — never at build time, since the image must not depend on a database.

**If the database disappears later**, no Compose feature helps. The backend uses `pool_pre_ping`,
so a dead pooled connection is replaced on the next checkout; while Postgres is down, requests
fail with `500` and `GET /api/v1/health/ready` answers `503`. `restart: unless-stopped` brings a
crashed container back.

**Dev-only, wrong in production**, all in `docker-compose.override.yml` or marked in the base file:
bind-mounted source, `uvicorn --reload` and `next dev`, the published database port, the default
`peach/peach` credentials. `docker compose -f docker-compose.yml up --build` runs the
production-shaped images without the override.

**Dockerfile vs Compose.** A Dockerfile answers *how one service is built and started*; it moves
unchanged to Lambda, ECS or Cloud Run. The Compose file answers *how services find and wait for
each other on one machine*; on AWS it is replaced by the CloudFormation stacks in §12.

| URL | What |
|---|---|
| http://localhost:3000 | frontend |
| http://localhost:8000/docs | API docs (Swagger) |
| http://localhost:8000/health | liveness |

---

## 7. Data model

Schema changes land only through Alembic revisions. `Base.metadata.create_all()` is used by the
test suite only — a migration is a versioned, reviewable, reversible change to a schema that
already holds rows; `create_all` is none of those.

**`users`** ★

| Column | Type | Rules |
|---|---|---|
| `id` | `uuid` | primary key, `gen_random_uuid()` |
| `cognito_sub` | `varchar(64)` | not null, unique — the identity; email can change, `sub` cannot |
| `email` | `varchar(320)` | not null |
| `name` | `varchar(120)` | not null |
| `created_at`, `updated_at` | `timestamptz` | not null, `now()` |

**`items`**

| Column | Type | Rules |
|---|---|---|
| `id` | `uuid` | primary key, `gen_random_uuid()` |
| `owner_id` | `uuid` | ★ not null, `references users(id) on delete cascade`, indexed |
| `name` | `varchar(120)` | not null |
| `description` | `text` | nullable, ≤ 2000 chars (enforced by the API) |
| `status` | `varchar(20)` | not null, default `todo`, check `in ('todo','in_progress','done')` |
| `created_at`, `updated_at` | `timestamptz` | not null, `now()`; `updated_at` bumped on every update |

**Migrations**

| Revision | Change |
|---|---|
| `0001` | create `items` (with `is_done`) |
| `0002` | replace `is_done` with three-state `status` |
| `0003` ★ | create `users`; add `items.owner_id` — rows without an owner are deleted (no deployed database holds data yet), then the column becomes not null with its foreign key and index. Downgrade drops both. |

---

## 8. API contract

**Conventions.** Base path `/api/v1`. JSON in and out. Ids are UUID strings (lowercase,
hyphenated). Timestamps are ISO 8601 in UTC with a `Z` suffix, e.g. `2026-09-30T14:05:09.123456Z`.
Errors use FastAPI's shape `{"detail": "..."}` (validation errors: `{"detail": [ ... ]}`, `422`).

**Authentication.** Every route under `/api/v1` requires `Authorization: Bearer <Cognito ID token>`;
it is declared once on the router, so a new route cannot be added unprotected. Only `GET /health`
is public.

| Condition | Response |
|---|---|
| no or malformed header, bad signature, wrong issuer/audience, expired, `token_use != "id"` | `401`, `WWW-Authenticate: Bearer` |
| no user pool configured on the server | `503` — never an open door |
| someone else's item | `404`, indistinguishable from a missing one |

**Endpoints**

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| `GET` | `/health` | — | `200 {"status":"ok"}` — touches nothing | — |
| `POST` | `/local/sign-in` ★ | `{"email", "name"?}` | `200 {"id_token"}` — **local development only** (§9); absent everywhere else | `422` |
| `GET` | `/api/v1/health/ready` | — | `200 {"status":"ok","database":"ok"}` | `503` if `SELECT 1` fails |
| `GET` | `/api/v1/me` ★ | — | `200 UserRead` | `401` |
| `GET` | `/api/v1/items` | — | `200 {"items": ItemRead[], "total": int}` | `422` on bad `limit`/`offset` |
| `POST` | `/api/v1/items` | `ItemCreate` | `201 ItemRead` | `422` |
| `GET` | `/api/v1/items/{id}` | — | `200 ItemRead` | `404` |
| `PATCH` | `/api/v1/items/{id}` | `ItemUpdate` | `200 ItemRead` | `404`, `422` |
| `DELETE` | `/api/v1/items/{id}` | — | `204` | `404` |

`GET /items` takes `limit` (1–100, default 20) and `offset` (≥ 0, default 0), ordered by
`created_at` descending; `total` counts all of the caller's items.

**Schemas**

| Schema | Field | Type | Rules |
|---|---|---|---|
| `ItemCreate` | `name` | string | 1–120 chars, required |
| | `description` | string \| null | ≤ 2000 chars, default null |
| | `status` | `"todo"` \| `"in_progress"` \| `"done"` | default `"todo"` |
| `ItemUpdate` | same three fields | | all optional; only fields sent are changed |
| `ItemRead` | `ItemCreate` fields + `id`, `created_at`, `updated_at` | | `owner_id` is never exposed |
| `UserRead` ★ | `id`, `email`, `name`, `created_at` | | |

Swagger at `/docs`, ReDoc at `/redoc`, the schema at `/openapi.json`.

---

## 9. Authentication ★

**Cognito** (`infra/cognito.yaml`, stack `<project>-cognito`):

- user pool — email is the username, email verified by code, password ≥ 8 chars with a number;
  standard attribute `name` is required at sign-up;
- one public app client (no secret — it lives in the browser): flows `USER_PASSWORD_AUTH` and
  `REFRESH_TOKEN_AUTH`; OAuth code flow with scopes `openid email profile`; callback URLs
  `http://localhost:3000/auth/callback` and `https://app.<domain>/auth/callback` (plus the
  `*.cloudfront.net` URL once it exists);
- hosted domain `<project>-<account id>.auth.us-east-1.amazoncognito.com` — used only by Google;
- Google identity provider only when `GOOGLE_CLIENT_ID` is set; off by default.

**Backend** (`app/auth.py`):

1. read the bearer token; none → `401`; pool not configured → `503`;
2. verify the RS256 signature against the pool's JWKS — from `COGNITO_JWKS` when set (Lambda has
   no internet route), otherwise fetched once from the issuer and cached;
3. check `iss` = the pool, `aud` = the app client, `exp`, `token_use == "id"`;
4. find the `users` row by `sub`, create it on first sight, refresh `email`/`name` if the token
   carries new values (`name` falls back to the part of the email before `@`);
5. `CurrentUser` is that row; every service call is scoped to its `id`.

**Frontend** (`lib/auth.ts`):

- email + password: Cognito's public `InitiateAuth` / `SignUp` / `ConfirmSignUp` /
  `ResendConfirmationCode` API, called from the browser; Google: hosted domain, authorization code
  + PKCE, exchanged on `/auth/callback`;
- tokens in `localStorage`; the ID token is renewed from the refresh token a minute before it
  expires; `getIdToken()` returns a valid token or null;
- `useSession()` returns `{ email, name }` from the ID token's claims, or null, and re-renders on
  sign-in/sign-out (also across tabs); `signOut()` clears storage;
- a `401` from the API signs the browser out.

**Local sign-in** ★ (`app/dev_auth.py`, `components/local-sign-in.tsx`) — so that
`docker compose up` works on a fresh checkout with no AWS account:

- the API mints RS256 ID tokens for any email at `POST /local/sign-in` (no password; the same
  email maps to the same `sub`, so the same board), signed by a key kept in the container's temp
  dir; `app/auth.py` verifies them with the same checks as Cognito's, against that key, a local
  issuer and audience;
- the frontend shows this form instead of the Cognito one whenever it was built without
  `COGNITO_CLIENT_ID`; tokens last 12 hours and are not refreshed;
- three guards keep it off AWS: it needs `APP_ENV=development` (the Lambda stack runs
  `production`), no pool configured, and no `AWS_LAMBDA_FUNCTION_NAME`; and `deploy-frontend.sh`
  refuses to build without the pool ids. Once `make deploy-cognito` has run, local sign-in turns
  itself off and local development uses the real pool.

`AuthGate` is a convenience — the static export has no server to refuse a page; the real
boundary is the API.

---

## 10. Frontend

| Route | Access | What it shows |
|---|---|---|
| `/` ★ | public | sign in: email + password, "Continue with Google" when enabled, link to `/signup`; a signed-in visitor goes straight to `/home` |
| `/signup` ★ | public | name, email, password → then the emailed 6-digit code; resend link; link back to `/` |
| `/auth/callback` ★ | public | exchanges the Google code, then `/home`; on failure an error with a link back to `/` |
| `/home` | signed in | dashboard (below) |
| `/items` | signed in | board: one column per status, drag cards between columns (optimistic, rolled back on error), click a card to edit or delete, "Add task" per column |
| `/items/list` ★ | signed in | the same tasks grouped by status in collapsible sections; click a row to edit, "Add task" per group; `#status-<status>` jumps to a group |
| 404 ★ | public | not found, with a link to `/home` and one to `/` |

Board and List are two tabs over the same data; the sidebar, the dashboard and both views read
one query (`useItems`), and one set of dialogs (`task-dialogs.tsx`) serves them all, so "+ Task"
works from any page.

**Visual language** — modelled on ClickUp's product screens, with Peach's own name and mark:

- workspace chrome: grey backdrop, a black icon rail on the left (active item glows on the
  violet→blue gradient), a white sidebar and a white page panel with 16px corners;
- statuses: solid upper-case pills (`TO DO` grey `#6b7280`, `IN PROGRESS` blue `#1e6feb`,
  `DONE` green `#1b7f51`, all ≥ 4.5:1 with white text) and a round status icon before every
  task; board columns carry a soft wash of the same hue;
- accent `#6647f0`; gradients from the brand kit (`#ff02f0→#f76808` for the mark,
  `#6647f0→#0091ff` for active and progress);
- type: Plus Jakarta Sans for headings, Inter for everything else (both OFL, via `next/font`);
- light theme first; dark tokens track it. Tokens live in `app/globals.css` only.

**Dashboard** (`task-dashboard.tsx`) ★ — built from `GET /items`, paged at `limit=100` until
`total` is reached:

- share of tasks done: headline percentage and a meter;
- a stacked bar of tasks by status, with legend and hover tooltips;
- one tile per status with its count, linking to `/items`;
- this week (Monday–Sunday, local time): tasks added (`created_at`) and completed (status `done`,
  `updated_at` this week — there is no `completed_at` column, so editing a done task re-counts it);
- "In progress" and "Recently completed" lists, five each, newest first.

**Every data screen has four states:** loading (`Skeleton`), empty (a card with a call to action
to `/items`), error (`Alert` with a Retry button), and data. Signed-in pages always show the
header with navigation and Log out.

**Data access.** Only `lib/api.ts` calls `fetch`. It attaches the token, throws a typed `ApiError`
on non-2xx, and parses every response with zod schemas that mirror §8. Server state lives in
TanStack Query; mutations update the cache optimistically and invalidate it on settle.

**Build targets.** `NEXT_OUTPUT=standalone` for the Compose image; `NEXT_OUTPUT=export` for S3.
Every route prerenders, so the export needs no server. `NEXT_PUBLIC_*` values are compiled in at
build time — changing them means rebuilding.

---

## 11. Backend layers

| Layer | Folder | Holds | Never holds |
|---|---|---|---|
| HTTP | `app/api/routes/` | parsing, status codes, dependencies | queries |
| Auth | `app/auth.py` | token verification, the current user | business rules |
| Logic | `app/services/` | queries and rules, always scoped by owner | HTTP types |
| Persistence | `app/models/` | ORM classes | behaviour |
| Contract | `app/schemas/` | Pydantic request/response models | ORM objects |

Async all the way: async SQLAlchemy sessions, `async def` handlers, no blocking I/O. One session
per request — committed on success, rolled back on error.

---

## 12. AWS

Everything in **us-east-1**, every resource tagged `PROJECT_NAME=peach`. Created from the
`Makefile` with an IAM user's CLI profile (root user: MFA on, never used for this).

```
browser ─► app.<domain> ─► CloudFront ─► private S3 bucket          (frontend)
browser ─► api.<domain> ─► CloudFront ─► Lambda function URL        (backend)
                                          └─► Lambda (FastAPI, in VPC) ─► Aurora Serverless v2
browser ─► Cognito (sign-in, token refresh)
```

| Stack | Template | Contains | Created by |
|---|---|---|---|
| `peach-cognito` ★ | `cognito.yaml` | user pool, app client, hosted domain, Google IdP (optional) | `make deploy-cognito` |
| `peach-backend` | `backend.yaml` | Lambda + function URL, Aurora Serverless v2 (scales to 0), security groups, DB secret, logs | `make deploy-backend` |
| `peach-api-edge` ★ | `api-edge.yaml` | CloudFront distribution in front of the function URL, `api.<domain>` alias | `make domain-backend` |
| `peach-frontend` | `frontend.yaml` | private bucket, origin access control, clean-URL rewrite function, distribution, `app.<domain>` alias | `make deploy-frontend`, `make domain` |
| `peach-github-oidc` | `github-oidc.yaml` | OIDC provider, deploy role | `make github-role` |
| ECR repository | — | backend images, last 3 kept | `deploy-backend.sh` |

**Frontend.** S3 stores the files; CloudFront serves them from the edge, terminates HTTPS and is
the only reader of the bucket (origin access control + bucket policy). Every deploy invalidates
the cache. Hashed assets are cached for a year, HTML never.

**Backend.** The image (Dockerfile `lambda` stage, arm64) is pushed to ECR tagged with the commit
SHA, the stack is updated to that tag, then the function is invoked with `{"action":"migrate"}`.
Rollback is deploying the previous tag.

**`api.<domain>`** ★ — a function URL cannot carry a custom domain, so a second CloudFront
distribution sits in front of it: caching disabled, all methods allowed, the `Host` header *not*
forwarded (the function URL rejects foreign hosts), `Authorization` forwarded. Once it exists,
`BACKEND_URL` becomes `https://api.<domain>` and the frontend is rebuilt against it.

**Domain and HTTPS.** Both certificates are requested in ACM in us-east-1 (the only region
CloudFront accepts) and are free. DNS records, four in total:

| Purpose | Name | Type | Value |
|---|---|---|---|
| prove control (frontend cert) | `_<token>.app.<domain>` | CNAME | given by ACM |
| prove control (API cert) | `_<token>.api.<domain>` | CNAME | given by ACM |
| route | `app.<domain>` | CNAME (or Route 53 alias) | the frontend distribution's `*.cloudfront.net` |
| route | `api.<domain>` | CNAME (or Route 53 alias) | the API distribution's `*.cloudfront.net` |

CloudFront redirects HTTP to HTTPS on both. With the zone in Route 53 the scripts write all four
records; otherwise they print them and wait until they resolve.

**Teardown**, in this order: `make destroy-frontend`, `make destroy-backend-domain` ★,
`make destroy-backend`, `make destroy-cognito`, then delete the certificates and the
`peach-github-oidc` stack. Nothing here bills by the hour while idle except Aurora's storage and
one Secrets Manager secret (~$0.50/month together).

---

## 13. Makefile — the deploy contract

CI has no recipe of its own: it runs these targets, so a failed deploy is debugged locally.

| Target | Does |
|---|---|
| `up`, `down`, `clean`, `logs`, `ps` | Compose lifecycle (`clean` wipes the database volume) |
| `migrate`, `revision m="..."` | Alembic inside the running backend |
| `test`, `lint`, `fmt` | both sides, inside the containers |
| `deploy-cognito` ★, `destroy-cognito` ★ | the user pool |
| `deploy-backend`, `destroy-backend`, `migrate-backend`, `logs-backend` | the API stack |
| `domain-backend DOMAIN=api.<domain>` ★, `destroy-backend-domain` ★ | the API's custom domain |
| `deploy-frontend`, `destroy-frontend` | the site |
| `cert DOMAIN=…`, `domain DOMAIN=app.<domain>` | the site's certificate and custom domain |
| `github-role` | the OIDC role and repository variables |

---

## 14. CI/CD ★

**`ci.yml`** — on every pull request and every push to `main`; also callable by `deploy.yml`
(which then takes over the push to `main`). Jobs in parallel:

| Job | Runs |
|---|---|
| backend-lint | `ruff check`, `ruff format --check` |
| backend-test | `pytest` against a `postgres:17-alpine` service container |
| frontend-lint | `eslint`, `prettier --check`, `tsc --noEmit` |
| frontend-test | `vitest run` |

**`deploy.yml`** — on every push to `main`, and by hand (`workflow_dispatch`):

1. `checks` — calls `ci.yml`; nothing deploys unless it is green;
2. `backend` — assumes the role, `make deploy-backend` (image tagged with the commit SHA);
3. `frontend` — after `backend`: assumes the role, `make deploy-frontend`.

One deploy at a time (`concurrency`, never cancelled halfway — an interrupted CloudFormation
update is worse than a queued one). The job summary shows the commit, both URLs and the result.

**OIDC, no keys.** GitHub issues a signed token for the run; AWS trusts GitHub's OIDC provider and
lets that token assume the deploy role only when

```
aud = sts.amazonaws.com
sub = repo:yurleomel/OOAD_Lab2:ref:refs/heads/main
```

— this repository, this branch, nothing else. A wildcard in `sub` would hand the AWS account to
any branch or pull request. The role's policy is scoped to the services the deploy drives
(★ extended with S3 put/list/delete on the site bucket and `cloudfront:CreateInvalidation`), not
`AdministratorAccess`. Credentials expire with the job.

**Repository variables** (not secrets — useless without a token minted by this repository):
`AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`, `PROJECT_NAME`, and for the frontend build `BACKEND_URL`,
`COGNITO_REGION`, `COGNITO_CLIENT_ID`, `COGNITO_DOMAIN`, `COGNITO_GOOGLE_ENABLED`. CI has no
`.env`; parameters it leaves empty keep the stack's current values.

---

## 15. Tests

Backend tests run against a real Postgres (`<db>_test`, created on first run, schema rebuilt per
session, each test in a rolled-back transaction). `tests/tokens.py` ★ generates an RSA key and
points the app at its JWKS before import, so tests mint real, signed tokens: `make_token(sub,
email, ...)` and `auth()` for the default user.

Covered, because they break silently:

| Path | Checks |
|---|---|
| auth ★ | no token, bad signature, expired, wrong audience, access token instead of ID token → `401`; no pool → `503`; `/health` stays public |
| local sign-in ★ | sign in then use the API; same email = same person; forged local token → `401`; off outside development, once a pool exists, and on Lambda |
| ownership | another user's item → `404` on read, update, delete; their list is empty |
| user provisioning ★ | first request creates the row, later ones reuse it, email/name refresh |
| items | create, validate, update partially, delete, paginate |
| lambda handler | a function URL event reaches the app; repeated calls survive |
| frontend | `api.ts` attaches the token, parses, raises `ApiError`, signs out on `401`; board drag/edit/rollback; list grouping, edit, add-in-group, collapse ★; `auth.ts` password flow, error mapping, refresh (shared, kept on network failure, sign-out on refusal), Google PKCE ★; gate redirect, sign-in/up forms ★; dashboard figures from a known list, paging past 100 ★ |

---

## 16. Out of scope

Not built, and not to be added without changing this file first: teams or sharing, roles,
background workers, queues, caches, a reverse proxy, a second database, WebSockets, file uploads,
email beyond Cognito's own, Kubernetes, multiple environments (staging), ECS/ALB.

---

## 17. Build order

1. Review and fix this file.
2. AWS account (root MFA, IAM user, `aws configure`) — needed from step 6 on, not before.
3. Generate the ★ backend pieces (auth, users, `/me`, migration 0003, tests) — `pytest` green.
4. Generate the ★ frontend pieces (auth, sign-in pages, gate, dashboard, tests) — lint, types,
   tests green.
5. `docker compose up --build`; sign in locally, add a task, reload — it is still there.
6. `ci.yml`; push one commit that fails the linter on purpose, see it red, fix it.
7. `make deploy-cognito`, `make deploy-backend`, `make deploy-frontend`; `make domain` and
   `make domain-backend`.
8. `make github-role`, `deploy.yml`; a push to `main` redeploys both.
9. Tear down what is no longer needed (§12).
