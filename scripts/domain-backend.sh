#!/usr/bin/env bash
# Put a custom domain, with HTTPS, in front of the API: an ACM certificate in
# us-east-1 and the CloudFront distribution in infra/api-edge.yaml, whose
# origin is the backend's Lambda function URL. Then BACKEND_URL becomes
# https://<domain>, locally and for CI, so the site is built against it.
#
#   make domain-backend DOMAIN=api.example.com
#
# Idempotent: an existing certificate is reused, and re-running after DNS is in
# place just re-checks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
TEMPLATE="${ROOT}/infra/api-edge.yaml"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

if [[ -f "${ENV_FILE}" ]]; then
  # Variables already exported win over .env: `AWS_REGION=eu-central-1 make x`
  # must not be quietly reset to the region .env names.
  preset="$(export -p)"
  set -a
  # shellcheck disable=SC1090,SC1091
  source "${ENV_FILE}"
  set +a
  eval "${preset}"
fi

for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
STACK_NAME="${API_EDGE_STACK_NAME:-${PROJECT_NAME}-api-edge}"
BACKEND_STACK_NAME="${STACK_NAME_BACKEND:-${PROJECT_NAME}-backend}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

# `make domain-backend DOMAIN=api.example.com` wins over what .env remembers.
DOMAIN="${DOMAIN:-${API_DOMAIN_NAME:-}}"
DOMAIN="${DOMAIN%.}"
[[ -n "${DOMAIN}" ]] || die "no domain - run: make domain-backend DOMAIN=api.example.com"

for tool in aws python3; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done
aws sts get-caller-identity >/dev/null 2>&1 \
  || die "no usable AWS credentials - set AWS_PROFILE or the AWS_* keys in .env"

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
  log "wrote ${1} to .env"
}

# shellcheck source-path=SCRIPTDIR source=lib/domain.sh
source "${ROOT}/scripts/lib/domain.sh"

# --- the origin: the backend's function URL --------------------------------

FUNCTION_URL="$(aws cloudformation describe-stacks --stack-name "${BACKEND_STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text 2>/dev/null || true)"
[[ -n "${FUNCTION_URL}" && "${FUNCTION_URL}" != "None" ]] \
  || die "stack ${BACKEND_STACK_NAME} has no ApiUrl - run make deploy-backend first"
ORIGIN="${FUNCTION_URL#https://}"
ORIGIN="${ORIGIN%%/*}"
log "origin ${ORIGIN}"

# --- DNS and certificate ----------------------------------------------------

resolve_hosted_zone
ensure_certificate

# --- the distribution -------------------------------------------------------

if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}" >/dev/null 2>&1; then
  log "creating ${STACK_NAME} (CloudFront takes a few minutes)"
else
  log "updating ${STACK_NAME}"
fi

if ! aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --parameter-overrides \
    "ProjectName=${PROJECT_NAME}" \
    "DomainName=${DOMAIN}" \
    "AcmCertificateArn=${CERT_ARN}" \
    "OriginDomain=${ORIGIN}" \
    "HostedZoneId=${ZONE_ID}" \
  --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"; then
  warn "deploy failed - most recent failure reasons:"
  aws cloudformation describe-stack-events --stack-name "${STACK_NAME}" \
    --max-items 40 \
    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`||ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
    --output table >&2 || true
  exit 1
fi

TARGET="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionDomainName'].OutputValue" --output text)"

# From now on the site talks to the API through its own domain.
env_set API_DOMAIN_NAME "${DOMAIN}"
env_set BACKEND_URL "https://${DOMAIN}"

# CI builds the site from repository variables, not .env.
REPO="${GITHUB_REPO:-$(git -C "${ROOT}" remote get-url origin 2>/dev/null \
  | sed -E 's#^.*github\.com[:/]##; s#\.git$##')}"
if [[ "${REPO}" == */* ]] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh variable set BACKEND_URL --repo "${REPO}" --body "https://${DOMAIN}"
  log "set the BACKEND_URL repository variable on ${REPO}"
else
  warn "set the repository variable BACKEND_URL=https://${DOMAIN} by hand"
fi

[[ -n "${ZONE_ID}" ]] || print_routing_record "${TARGET}"

echo "  https://${DOMAIN} - the function URL keeps working too"
echo
echo "Rebuild the site against it - make deploy-frontend, or push to main."
