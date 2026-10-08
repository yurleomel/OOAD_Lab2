# Peach — notes for agents

Read `PROJECT.md` first: it is the specification, and code is generated from it. `README.md` is the
upstream course document, kept as reference. Items marked ★ in `PROJECT.md` were missing from the
upstream repository and are being written here.

## Status of the ★ items

| Area | State |
|---|---|
| Backend: auth, users, `/me`, migration `0003`, local sign-in, tests | done — `pytest` 46 passed |
| Frontend: `lib/auth.ts`, sign-in pages, `AuthGate`, `task-dashboard`, List view, ClickUp-style redesign | done — vitest 56 passed, static export builds |
| Local run: `docker compose up --build` with local sign-in (no AWS) | done — verified in a browser: sign in, add, reload, per-user isolation |
| Cognito: `infra/cognito.yaml`, `deploy-cognito.sh`, `destroy-cognito.sh` | deployed (pool `us-east-1_qEVU77JkT`, Essentials tier, managed login v2 + default branding, logout URLs) |
| Lab 4: `/login` opens Cognito's managed login (password + Google); log out goes through the domain's `/logout` | code + Cognito stack done. Google still off: needs `GOOGLE_CLIENT_ID`/`_SECRET` in `.env`, `make deploy-cognito`, repo variable `COGNITO_GOOGLE_ENABLED=true`, then a site deploy |
| AWS: backend on Lambda + RDS PostgreSQL, site on S3 + CloudFront | live - site https://app.mylanora.world, API https://api.mylanora.world (behind them d6qjoq19m7ta0.cloudfront.net and the function URL ama23qrervq2gu4uepqxl7jcce0stitq.lambda-url.us-east-1.on.aws); Cognito sign-in checked end to end on both |
| API domain: `api-edge.yaml`, `domain-backend.sh` | not started |
| CI: `ci.yml` - ruff, pytest on Postgres, eslint/prettier/tsc, vitest | done |
| CD: `deploy.yml`, OIDC role `peach-github-deploy` (trusts this repo's `main` only), repo variables | done - every push to `main` checks, then ships the backend (image tagged with the SHA) and the site |
| Custom domain for `app.` / `api.` (`api-edge.yaml`, `domain-backend.sh`) | done - `mylanora.world` at Namecheap, 4 CNAMEs by hand; HTTP redirects to HTTPS |

## Running

```bash
docker compose up -d --build        # then http://localhost:3000 - sign in with any email
docker compose run --rm --no-deps backend sh -c "ruff check . && pytest -q"   # backend checks
docker compose run --rm --no-deps backend alembic check                         # models vs migrations
docker compose run --rm --no-deps frontend sh -c "pnpm lint && pnpm format:check && pnpm exec tsc --noEmit && pnpm test"
docker compose run --rm --no-deps -e NODE_ENV=production -e NEXT_OUTPUT=export frontend pnpm build
```

## Gotchas

- Without `COGNITO_*` the app runs in local sign-in mode (`app/dev_auth.py`): any email, no
  password, tokens signed by the backend container. It is on only with `APP_ENV=development`, no
  pool, and not on Lambda; without it (e.g. `APP_ENV=production` and no pool) every `/api/v1`
  route answers `503`. After `make deploy-cognito` rebuild both services to switch to Cognito.
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
- Remotes: `origin` is the student repository, `upstream` is the course repository. Never push to
  `upstream`.
