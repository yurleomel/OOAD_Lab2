# Peach — notes for agents

Read `PROJECT.md` first: it is the specification, and code is generated from it. `README.md` is the
upstream course document, kept as reference. Items marked ★ in `PROJECT.md` were missing from the
upstream repository and are being written here.

## Status of the ★ items

| Area | State |
|---|---|
| Backend: auth, users, `/me`, migration `0003`, local sign-in, tests | done — `pytest` 46 passed |
| Frontend: `lib/auth.ts`, sign-in pages, `AuthGate`, `task-dashboard`, List view, ClickUp-style redesign | done — vitest 53 passed, static export builds |
| Local run: `docker compose up --build` with local sign-in (no AWS) | done — verified in a browser: sign in, add, reload, per-user isolation |
| Cognito: `infra/cognito.yaml`, `deploy-cognito.sh`, `destroy-cognito.sh` | written, passes `cfn-lint`; not deployed yet |
| API domain: `api-edge.yaml`, `domain-backend.sh` | not started |
| CI: `ci.yml` - ruff, pytest on Postgres, eslint/prettier/tsc, vitest | done |
| CD: `deploy.yml`, S3/CloudFront rights on the OIDC role | not started (needs AWS) |

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
- Remotes: `origin` is the student repository, `upstream` is the course repository. Never push to
  `upstream`.
