# Peach — notes for agents

Read `PROJECT.md` first: it is the specification, and code is generated from it. `README.md` is the
upstream course document, kept as reference. Items marked ★ in `PROJECT.md` were missing from the
upstream repository and are being written here.

## Status of the ★ items

| Area | State |
|---|---|
| Backend: auth, users, `/me`, migration `0003`, tests | done — `pytest` 38 passed |
| Frontend: `lib/auth.ts`, sign-in pages, `AuthGate`, `task-dashboard` | not started (styling decision pending) |
| Cognito: `infra/cognito.yaml`, `deploy-cognito.sh`, `destroy-cognito.sh` | not started |
| API domain: `api-edge.yaml`, `domain-backend.sh` | not started |
| CI/CD: `ci.yml`, `deploy.yml`, S3/CloudFront rights on the OIDC role | not started |

## Running

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm --no-deps backend sh -c "ruff check . && pytest -q"   # backend checks
docker compose run --rm --no-deps backend alembic check                         # models vs migrations
```

## Gotchas

- Until `make deploy-cognito` has written `COGNITO_*` to `.env`, every `/api/v1` route answers
  `503 Sign-in is not configured`. That is by design — there is no auth bypass anywhere.
- Backend tests need no Cognito: `tests/tokens.py` generates a key, hands its JWKS to the app via
  `COGNITO_JWKS`, and mints real signed tokens. Import it before `app.config` is first read.
- `docker compose exec backend …` only works while the backend is healthy; use
  `docker compose run --rm --no-deps backend …` when it is not.
- `frontend/AGENTS.md`: this Next.js version differs from training data — read its bundled docs
  before writing frontend code.
- Remotes: `origin` is the student repository, `upstream` is the course repository. Never push to
  `upstream`.
