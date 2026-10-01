#!/usr/bin/env bash
# Put a custom domain, with HTTPS, on the deployed frontend's CloudFront
# distribution. Only the frontend gets a custom domain - the API stays on its
# Lambda function URL - and it is assigned here, separately from
# `make deploy-frontend`, which never touches the domain settings.
#
#   scripts/domain-frontend.sh cert     request + DNS-validate an ACM certificate
#   scripts/domain-frontend.sh domain   the above, then attach it to the distribution
#
# Both are idempotent: an existing certificate for the domain is reused rather
# than re-requested, and re-running after DNS is in place just re-checks.
set -euo pipefail

MODE="${1:-domain}"
case "${MODE}" in
  cert | domain) ;;
  *) echo "usage: $0 [cert|domain]" >&2; exit 2 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
TEMPLATE="${ROOT}/infra/frontend.yaml"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
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

# A blank AWS_PROFILE is read as a profile literally named "", and blank keys
# short-circuit the credential chain. Treat empty as absent.
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
STACK_NAME="${FRONTEND_STACK_NAME:-${PROJECT_NAME}-frontend}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

# `make domain DOMAIN=app.example.com` wins over whatever .env remembers.
DOMAIN="${DOMAIN:-${DOMAIN_NAME:-}}"
DOMAIN="${DOMAIN%.}"
[[ -n "${DOMAIN}" ]] || die "no domain - run: make ${MODE} DOMAIN=app.example.com"

for tool in aws python3; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done
aws sts get-caller-identity >/dev/null 2>&1 \
  || die "no usable AWS credentials - set AWS_PROFILE or the AWS_* keys in .env"

# --- helpers ----------------------------------------------------------------

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

stack_output() {
  aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text 2>/dev/null || true
}

# --- hosted zone ------------------------------------------------------------

resolve_hosted_zone

# --- certificate ------------------------------------------------------------

ensure_certificate
# Only the domain is remembered. The zone and the certificate are looked up
# again on every run, so neither needs to live in .env.
env_set DOMAIN_NAME "${DOMAIN}"

if [[ "${MODE}" == "cert" ]]; then
  echo
  echo "Certificate ready. Attach it with: make domain"
  exit 0
fi

# --- attach -----------------------------------------------------------------

# Only the domain parameters change; every other parameter keeps the stack's
# current value, and the site itself is not rebuilt.
aws cloudformation describe-stacks --stack-name "${STACK_NAME}" >/dev/null 2>&1 \
  || die "stack ${STACK_NAME} does not exist yet - run make deploy-frontend first"

log "attaching ${DOMAIN} to the distribution (CloudFront takes a few minutes)"
if ! aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --parameter-overrides \
    "DomainName=${DOMAIN}" \
    "AcmCertificateArn=${CERT_ARN}" \
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

TARGET="$(stack_output DistributionDomainName)"

[[ -n "${ZONE_ID}" ]] || print_routing_record "${TARGET}"

echo "  https://${DOMAIN} - the cloudfront.net name keeps working too"
echo
echo "Let the API accept the new origin:"
echo
echo "  API_CORS_ORIGINS=https://${DOMAIN}   in .env, then: make deploy-backend"
