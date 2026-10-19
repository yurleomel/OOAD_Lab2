#!/usr/bin/env bash
# Deploy the agenda parser (infra/ai.yml): its function and public URL, the
# role that may call Bedrock, and the account's $5 monthly budget alarm.
#
# The image and the Cognito ids come from the live backend function, so the
# parser runs the API's code and accepts the API's tokens; make deploy-backend
# comes first. Writes PARSER_URL to .env (deploy-frontend.sh builds against it)
# and to the repository variable CI uses. Safe to re-run.
#
#   PARSER_API     converse (default) or messages; a plain re-run goes back to converse
#   PARSER_MODEL   default us.anthropic.claude-haiku-4-5-20251001-v1:0, the same
#                  way back. The lab's: PARSER_API=messages PARSER_MODEL=anthropic.claude-opus-5-5
#   BUDGET_EMAIL   who the budget alarm emails (default: the first REPORT_RECIPIENTS)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/infra/ai.yml"
ENV_FILE="${ROOT}/.env"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

if [[ -f "${ENV_FILE}" ]]; then
  # Variables already exported win over .env: `PARSER_MODEL=… make x` must
  # not be quietly reset to what .env names.
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
STACK_NAME="${AI_STACK_NAME:-${PROJECT_NAME}-ai}"
BACKEND_STACK="${STACK_NAME_BACKEND:-${PROJECT_NAME}-backend}"
FRONTEND_STACK="${STACK_NAME_FRONTEND:-${PROJECT_NAME}-frontend}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

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

for tool in aws python3; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "no usable AWS credentials - set AWS_PROFILE or the AWS_* keys in .env"
log "account ${ACCOUNT_ID} in ${AWS_REGION}"

# --- what the backend already has -------------------------------------------

aws cloudformation describe-stacks --stack-name "${BACKEND_STACK}" >/dev/null 2>&1 \
  || die "stack ${BACKEND_STACK} does not exist - run make deploy-backend first"

BACKEND_FUNCTION="$(aws cloudformation describe-stacks --stack-name "${BACKEND_STACK}" \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionName'].OutputValue" --output text)"
backend_env() {
  aws lambda get-function-configuration --function-name "${BACKEND_FUNCTION}" \
    --query "Environment.Variables.$1" --output text
}

IMAGE_URI="${AI_IMAGE_URI:-$(aws lambda get-function --function-name "${BACKEND_FUNCTION}" \
  --query Code.ImageUri --output text)}"
ARCHITECTURE="$(aws lambda get-function-configuration --function-name "${BACKEND_FUNCTION}" \
  --query 'Architectures[0]' --output text)"
POOL_ID="$(backend_env COGNITO_USER_POOL_ID)"
CLIENT_ID="$(backend_env COGNITO_CLIENT_ID)"
[[ -n "${POOL_ID}" && "${POOL_ID}" != "None" ]] \
  || die "the backend has no Cognito pool - the parser would accept nobody (make deploy-cognito)"

# Every origin the site is served from, plus the local one.
ORIGINS="http://localhost:3000"
if aws cloudformation describe-stacks --stack-name "${FRONTEND_STACK}" >/dev/null 2>&1; then
  for key in SiteUrl DistributionDomainName; do
    value="$(aws cloudformation describe-stacks --stack-name "${FRONTEND_STACK}" \
      --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue" --output text)"
    [[ "${value}" == https://* ]] || value="https://${value}"
    [[ ",${ORIGINS}," == *",${value},"* ]] || ORIGINS="${ORIGINS},${value}"
  done
fi

BUDGET_EMAIL="${BUDGET_EMAIL:-${REPORT_RECIPIENTS%%,*}}"
BUDGET_EMAIL="${BUDGET_EMAIL// /}"
[[ -n "${BUDGET_EMAIL}" ]] || warn "BUDGET_EMAIL and REPORT_RECIPIENTS are empty - no budget alarm"

PARSER_API="${PARSER_API:-converse}"
log "image ${IMAGE_URI##*/} (${ARCHITECTURE}), api ${PARSER_API}, model ${PARSER_MODEL:-us.anthropic.claude-haiku-4-5-20251001-v1:0}"
log "origins ${ORIGINS}"

# --- deploy -----------------------------------------------------------------

PARAMS_FILE="$(mktemp)"
trap 'rm -f "${PARAMS_FILE}"' EXIT

PROJECT_NAME="${PROJECT_NAME}" \
IMAGE_URI="${IMAGE_URI}" \
ARCHITECTURE="${ARCHITECTURE}" \
POOL_ID="${POOL_ID}" \
CLIENT_ID="${CLIENT_ID}" \
API="${PARSER_API}" \
MODEL="${PARSER_MODEL:-us.anthropic.claude-haiku-4-5-20251001-v1:0}" \
ORIGINS="${ORIGINS}" \
BUDGET_EMAIL="${BUDGET_EMAIL}" \
python3 - "${PARAMS_FILE}" <<'PY'
import json, os, sys

env = os.environ
params = {
    "ProjectName": env["PROJECT_NAME"],
    "ImageUri": env["IMAGE_URI"],
    "Architecture": env["ARCHITECTURE"],
    "CognitoUserPoolId": env["POOL_ID"],
    "CognitoClientId": env["CLIENT_ID"],
    "ParserApi": env["API"],
    "ParserModel": env["MODEL"],
    "AllowedOrigins": env["ORIGINS"],
    "BudgetEmail": env["BUDGET_EMAIL"],
}
json.dump([{"ParameterKey": k, "ParameterValue": v} for k, v in params.items()],
          open(sys.argv[1], "w"))
PY

log "deploying ${STACK_NAME}"
if ! aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --parameter-overrides "file://${PARAMS_FILE}" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"; then
  warn "deploy failed - most recent failure reasons:"
  aws cloudformation describe-stack-events --stack-name "${STACK_NAME}" \
    --max-items 40 \
    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`||ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
    --output table >&2 || true
  exit 1
fi

output() {
  aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

PARSER_URL="$(output ParserUrl)"
env_set PARSER_URL "${PARSER_URL}"

# CI builds the site from repository variables, not .env.
REPO="${GITHUB_REPO:-$(git -C "${ROOT}" remote get-url origin 2>/dev/null \
  | sed -E 's#^.*github\.com[:/]##; s#\.git$##')}"
if [[ "${REPO}" == */* ]] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh variable set PARSER_URL --repo "${REPO}" --body "${PARSER_URL}"
  log "set the PARSER_URL repository variable on ${REPO}"
else
  warn "set the repository variable PARSER_URL=${PARSER_URL} by hand"
fi

# Without a token the answer must be 401, never a parse.
status="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST "${PARSER_URL}" \
  -H 'content-type: application/json' -d '{}' || true)"
if [[ "${status}" == "401" ]]; then
  log "POST without a token answered 401"
else
  warn "POST without a token answered ${status}, expected 401 - check: make parse-logs"
fi

echo
echo "  parser     ${PARSER_URL}"
echo "  model      ${PARSER_API} ${PARSER_MODEL:-us.anthropic.claude-haiku-4-5-20251001-v1:0}"
echo "  logs       make parse-logs"
[[ -z "${BUDGET_EMAIL}" ]] || echo "  budget     $(output BudgetName): \$5/month, alarms by email"
echo
echo "Next: make deploy-frontend (it builds the Paste an agenda screen against PARSER_URL)."
