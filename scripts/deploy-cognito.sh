#!/usr/bin/env bash
# Create or update the Cognito user pool in infra/cognito.yaml, then write its
# ids into .env - COGNITO_REGION, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID,
# COGNITO_DOMAIN, COGNITO_GOOGLE_ENABLED - and print them.
#
# Safe to re-run, and worth re-running after the first `make deploy-frontend`
# or `make domain`: each run registers every site URL it can find as an OAuth
# redirect, so Google sign-in may return there.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/infra/cognito.yaml"
ENV_FILE="${ROOT}/.env"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# --- configuration ----------------------------------------------------------

if [[ -f "${ENV_FILE}" ]]; then
  # Variables already exported win over .env: `AWS_REGION=eu-central-1 make x`
  # must not be quietly reset to the region .env names.
  preset="$(export -p)"
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
  eval "${preset}"
fi

# A .env full of empty placeholders must not short-circuit the credential chain.
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
STACK_NAME="${COGNITO_STACK_NAME:-${PROJECT_NAME}-cognito}"
FRONTEND_STACK_NAME="${FRONTEND_STACK_NAME:-${PROJECT_NAME}-frontend}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

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

# --- preflight --------------------------------------------------------------

for tool in aws python3; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done
aws sts get-caller-identity >/dev/null 2>&1 \
  || die "no usable AWS credentials - run aws configure, or set AWS_PROFILE in .env"
log "deploying as $(aws sts get-caller-identity --query Arn --output text)"

if [[ -n "${GOOGLE_CLIENT_ID:-}" && -z "${GOOGLE_CLIENT_SECRET:-}" ]]; then
  die "GOOGLE_CLIENT_ID is set but GOOGLE_CLIENT_SECRET is not"
fi

# --- redirect URLs ----------------------------------------------------------

# Local Compose always; then whatever deployed addresses exist so far.
CALLBACKS=("http://localhost:${FRONTEND_PORT:-3000}/auth/callback")

SITE_URL="$(aws cloudformation describe-stacks --stack-name "${FRONTEND_STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='SiteUrl'].OutputValue" \
  --output text 2>/dev/null || true)"
if [[ -n "${SITE_URL}" && "${SITE_URL}" != "None" ]]; then
  CALLBACKS+=("${SITE_URL%/}/auth/callback")
fi
if [[ -n "${DOMAIN_NAME:-}" ]]; then
  CALLBACKS+=("https://${DOMAIN_NAME}/auth/callback")
fi
CALLBACK_LIST="$(printf '%s\n' "${CALLBACKS[@]}" | awk '!seen[$0]++' | paste -sd, -)"
log "OAuth redirects: ${CALLBACK_LIST}"

# --- deploy -----------------------------------------------------------------

# Parameters go through a 0600 file rather than argv, so the Google secret
# never shows up in `ps`. Every value is explicit: an empty Google id turns
# Google off rather than keeping whatever the stack had.
PARAMS_FILE="$(mktemp)"
chmod 600 "${PARAMS_FILE}"
trap 'rm -f "${PARAMS_FILE}"' EXIT

PROJECT_NAME="${PROJECT_NAME}" \
CALLBACK_LIST="${CALLBACK_LIST}" \
GOOGLE_ID="${GOOGLE_CLIENT_ID:-}" \
GOOGLE_SECRET="${GOOGLE_CLIENT_SECRET:-}" \
python3 - "${PARAMS_FILE}" <<'PY'
import json, os, sys

params = {
    "ProjectName": os.environ["PROJECT_NAME"],
    "CallbackUrls": os.environ["CALLBACK_LIST"],
    "GoogleClientId": os.environ["GOOGLE_ID"],
    "GoogleClientSecret": os.environ["GOOGLE_SECRET"],
}
with open(sys.argv[1], "w") as fh:
    json.dump([{"ParameterKey": k, "ParameterValue": v} for k, v in params.items()], fh)
PY

if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}" >/dev/null 2>&1; then
  log "first deploy - creating ${STACK_NAME}"
else
  log "updating ${STACK_NAME}"
fi

if ! aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --parameter-overrides "file://${PARAMS_FILE}" \
  --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"; then
  warn "deploy failed - most recent failure reasons:"
  aws cloudformation describe-stack-events --stack-name "${STACK_NAME}" \
    --max-items 40 \
    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`||ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
    --output table >&2 || true
  exit 1
fi

outputs() {
  aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

POOL_ID="$(outputs UserPoolId)"
CLIENT_ID="$(outputs ClientId)"
DOMAIN="$(outputs Domain)"
GOOGLE_ENABLED="$(outputs GoogleEnabled)"
GOOGLE_REDIRECT="$(outputs GoogleRedirectUri)"

env_set COGNITO_REGION "${AWS_REGION}"
env_set COGNITO_USER_POOL_ID "${POOL_ID}"
env_set COGNITO_CLIENT_ID "${CLIENT_ID}"
env_set COGNITO_DOMAIN "${DOMAIN}"
env_set COGNITO_GOOGLE_ENABLED "${GOOGLE_ENABLED}"

echo
echo "  COGNITO_REGION=${AWS_REGION}"
echo "  COGNITO_USER_POOL_ID=${POOL_ID}"
echo "  COGNITO_CLIENT_ID=${CLIENT_ID}"
echo "  COGNITO_DOMAIN=${DOMAIN}"
echo "  COGNITO_GOOGLE_ENABLED=${GOOGLE_ENABLED}"
echo
echo "Written to .env. None of these are secret - the frontend compiles them in."
echo "Rebuild so both services pick them up:  docker compose up --build"
if [[ "${GOOGLE_ENABLED}" != "true" ]]; then
  echo
  echo "Google is off. To add it, create an OAuth client in Google Cloud with this"
  echo "authorised redirect URI, put its id and secret in .env and re-run:"
  echo "  ${GOOGLE_REDIRECT}"
fi
echo
