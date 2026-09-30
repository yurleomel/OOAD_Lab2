#!/usr/bin/env bash
# Delete the Cognito stack - the user pool and every account in it - and clear
# the COGNITO_* ids from .env.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

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

for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
STACK_NAME="${COGNITO_STACK_NAME:-${PROJECT_NAME}-cognito}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

command -v aws >/dev/null 2>&1 || die "aws cli is required"
aws cloudformation describe-stacks --stack-name "${STACK_NAME}" >/dev/null 2>&1 \
  || die "stack ${STACK_NAME} does not exist in ${AWS_REGION}"

if [[ "${FORCE:-0}" != "1" ]]; then
  echo "This deletes stack ${STACK_NAME} in ${AWS_REGION}: the user pool and every"
  echo "account in it. Nobody will be able to sign in until make deploy-cognito."
  read -r -p "Type the stack name to confirm: " reply
  [[ "${reply}" == "${STACK_NAME}" ]] || die "aborted"
fi

log "deleting ${STACK_NAME}"
aws cloudformation delete-stack --stack-name "${STACK_NAME}"
aws cloudformation wait stack-delete-complete --stack-name "${STACK_NAME}"

if [[ -f "${ENV_FILE}" ]]; then
  python3 - "${ENV_FILE}" <<'PY'
import re, sys

path = sys.argv[1]
keys = ("COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID", "COGNITO_DOMAIN")
lines = [
    re.sub(rf"^({'|'.join(keys)})=.*", r"\1=", line)
    for line in open(path).read().splitlines()
]
lines = [re.sub(r"^COGNITO_GOOGLE_ENABLED=.*", "COGNITO_GOOGLE_ENABLED=false", l) for l in lines]
open(path, "w").write("\n".join(lines) + "\n")
PY
  log "cleared the COGNITO_* ids in .env"
fi

log "done"
