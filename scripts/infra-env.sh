#!/usr/bin/env bash
# Write what the app needs from infra/ into .env - COGNITO_REGION,
# COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, COGNITO_DOMAIN,
# COGNITO_GOOGLE_ENABLED and PARSER_URL - and print them. Reads the Terraform
# outputs from the HCP Terraform state; changes nothing in the cloud.
#
# Needs `terraform login` and `make infra-init` once. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

command -v terraform >/dev/null 2>&1 || die "terraform is required but not installed"

output() {
  terraform -chdir="${ROOT}/infra" output -raw "$1" 2>/dev/null \
    || die "no Terraform output $1 - run terraform login and make infra-init first"
}

# Rewrite one KEY=VALUE in .env, leaving every other line - credentials very
# much included - exactly as it was.
env_set() {
  KEY="$1" VALUE="$2" ENV_FILE="${ENV_FILE}" python3 - <<'PY'
import os, re

key, value, path = os.environ["KEY"], os.environ["VALUE"], os.environ["ENV_FILE"]
lines = open(path).read().splitlines() if os.path.exists(path) else []
pattern = re.compile(rf"^{re.escape(key)}=")

for i, line in enumerate(lines):
    if pattern.match(line):
        lines[i] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")

open(path, "w").write("\n".join(lines) + "\n")
PY
}

# .env key, Terraform output. (No associative arrays: macOS ships bash 3.2.)
echo
while read -r key name; do
  value="$(output "${name}")"
  env_set "${key}" "${value}"
  echo "  ${key}=${value}"
done <<'PAIRS'
COGNITO_REGION cognito_region
COGNITO_USER_POOL_ID cognito_user_pool_id
COGNITO_CLIENT_ID cognito_client_id
COGNITO_DOMAIN cognito_domain
COGNITO_GOOGLE_ENABLED cognito_google_enabled
PARSER_URL parser_url
PAIRS
echo

PARSER_URL="$(output parser_url)"
GOOGLE_ENABLED="$(output cognito_google_enabled)"

# CI builds the site from repository variables, not .env.
REPO="${GITHUB_REPO:-$(git -C "${ROOT}" remote get-url origin 2>/dev/null \
  | sed -E 's#^.*github\.com[:/]##; s#\.git$##')}"
if [[ "${REPO}" == */* ]] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh variable set PARSER_URL --repo "${REPO}" --body "${PARSER_URL}"
  log "set the PARSER_URL repository variable on ${REPO}"
else
  warn "set the repository variable PARSER_URL=${PARSER_URL} by hand"
fi

echo "Written to .env. None of these are secret - the frontend compiles them in."
echo "Rebuild so both services pick them up:  docker compose up --build"
if [[ "${GOOGLE_ENABLED}" != "true" ]]; then
  echo
  echo "Google is off. To add it, create an OAuth client in Google Cloud with this"
  echo "authorised redirect URI, set google_client_id in infra/terraform.tfvars and"
  echo "google_client_secret in the workspace, and merge:"
  echo "  $(output google_redirect_uri)"
fi
echo
