COMPOSE := docker compose

.PHONY: help up down build logs ps migrate revision test test-backend test-frontend lint fmt clean shell-backend shell-db deploy-backend destroy-backend logs-backend migrate-backend cert domain domain-backend destroy-backend-domain deploy-frontend destroy-frontend github-role report-now report-ls report-logs report-status report-local llm-hello parse parse-logs infra-init infra-plan infra-check infra-env

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the whole stack (detached)
	$(COMPOSE) up -d --build

down: ## Stop the stack
	$(COMPOSE) down

clean: ## Stop the stack and wipe the database volume
	$(COMPOSE) down -v

build: ## Rebuild images
	$(COMPOSE) build

logs: ## Tail all logs
	$(COMPOSE) logs -f

ps: ## Show service status
	$(COMPOSE) ps

migrate: ## Apply migrations
	$(COMPOSE) exec backend alembic upgrade head

revision: ## Autogenerate a migration: make revision m="add x"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	$(COMPOSE) exec backend pytest

test-frontend: ## Run frontend tests
	$(COMPOSE) exec frontend pnpm test

lint: ## Lint both sides
	$(COMPOSE) exec backend ruff check .
	$(COMPOSE) exec frontend pnpm lint

fmt: ## Format both sides
	$(COMPOSE) exec backend ruff format .
	$(COMPOSE) exec frontend pnpm format

shell-backend: ## Shell into the backend container
	$(COMPOSE) exec backend bash

shell-db: ## psql into the database
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-peach} -d $${POSTGRES_DB:-peach}

# Cognito, the weekly report and the agenda parser are Terraform in infra/. Plans
# and applies run in HCP Terraform (workspace peach-prod): a pull request gets a
# plan, a merge to main applies it. Nothing here applies.
infra-init: ## Connect infra/ to its HCP Terraform workspace (after terraform login)
	terraform -chdir=infra init

infra-plan: ## Plan infra/ in HCP Terraform against the real cloud; changes nothing
	terraform -chdir=infra plan

infra-check: ## terraform fmt -check and validate, offline (what CI runs)
	terraform fmt -check -recursive infra
	terraform -chdir=infra init -backend=false -input=false >/dev/null
	terraform -chdir=infra validate
	terraform -chdir=infra/bootstrap init -backend=false -input=false >/dev/null
	terraform -chdir=infra/bootstrap validate

infra-env: ## Write COGNITO_* and PARSER_URL from the Terraform outputs to .env
	./scripts/infra-env.sh

deploy-backend: ## Build + push the image, roll the Lambda (function URL + RDS PostgreSQL), migrate, write BACKEND_URL to .env
	./scripts/deploy-backend.sh

destroy-backend: ## Delete the backend stack, database included
	./scripts/destroy-backend.sh

logs-backend: ## Tail the deployed backend's CloudWatch logs
	aws logs tail /aws/lambda/$${PROJECT_NAME:-peach}-backend --follow --since 10m

migrate-backend: ## Re-run migrations on the deployed backend (deploy-backend already does)
	aws lambda invoke --function-name $${PROJECT_NAME:-peach}-backend \
		--cli-binary-format raw-in-base64-out --payload '{"action":"migrate"}' /dev/stdout

domain-backend: ## Give the API a custom domain with HTTPS: make domain-backend DOMAIN=api.example.com
	./scripts/domain-backend.sh

destroy-backend-domain: ## Delete the API's custom-domain distribution
	./scripts/destroy-backend-domain.sh

cert: ## Request + DNS-validate a us-east-1 certificate for the frontend: make cert DOMAIN=app.example.com
	./scripts/domain-frontend.sh cert

domain: ## Assign a custom domain to the frontend: make domain DOMAIN=app.example.com
	./scripts/domain-frontend.sh domain

deploy-frontend: ## Build the static export against BACKEND_URL and ship it to S3 + CloudFront
	./scripts/deploy-frontend.sh

destroy-frontend: ## Delete the frontend stack (bucket + distribution)
	./scripts/destroy-frontend.sh

github-role: ## Create the IAM role GitHub Actions assumes to deploy (OIDC, no keys)
	./scripts/github-role.sh

report-now: ## Queue a report on demand: make report-now WEEK=2026-W41 (no WEEK = last week)
	./scripts/report.sh now $(WEEK)

report-ls: ## List the reports in the bucket
	./scripts/report.sh ls

report-logs: ## The trigger lines of both report functions, last 24 h (SINCE_HOURS=…)
	./scripts/report.sh logs

report-status: ## Messages waiting in the report queue and its dead-letter queue
	./scripts/report.sh status

report-local: ## Print a report built from the Compose database: make report-local WEEK=2026-W40
	$(COMPOSE) exec backend python -m app.reports.weekly $(WEEK)

llm-hello: ## The first Bedrock call from the laptop: answer, stop_reason, usage
	./scripts/llm.sh hello

parse: ## Run the agenda parser from the laptop: make parse TEXT="Пн 10:00, синк ..."
	./scripts/llm.sh parse

parse-logs: ## The parser's JSON log lines, last 24 h (SINCE_HOURS=…)
	aws logs filter-log-events --log-group-name /aws/lambda/$${PROJECT_NAME:-peach}-agenda-parser \
		--start-time $$(( ($$(date +%s) - $${SINCE_HOURS:-24} * 3600) * 1000 )) \
		--filter-pattern '"agenda_parse"' --query 'events[].message' --output text | tr '\t' '\n'
