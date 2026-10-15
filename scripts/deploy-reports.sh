#!/usr/bin/env bash
# Deploy the weekly report (infra/reports.yaml) next to the backend: the
# builder and mailer functions, the reports bucket, the request queue and its
# dead-letter queue, the Monday schedule, the S3 gateway endpoint and the SES
# identity for the sending domain.
#
# Everything it shares with the API - the image, the VPC, the subnets, the
# security group, the database URL - it reads from the live backend stack, so
# make deploy-backend comes first. Safe to re-run.
#
#   REPORTS_MAIL_DOMAIN   send from reports@<domain>   (empty: keep the stack's)
#   REPORT_RECIPIENTS     comma-separated               (empty: keep the stack's)
#   REPORTS_SCHEDULE      default cron(0 7 ? * MON *), e.g. "rate(5 minutes)"
#   REPORTS_FAIL_WEEK     a week the builder refuses, for the dead-letter exercise
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/infra/reports.yaml"
ENV_FILE="${ROOT}/.env"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# --- configuration ----------------------------------------------------------

if [[ -f "${ENV_FILE}" ]]; then
  # Variables already exported win over .env: `REPORTS_FAIL_WEEK=… make x`
  # must not be quietly reset to what .env names.
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
STACK_NAME="${REPORTS_STACK_NAME:-${PROJECT_NAME}-reports}"
BACKEND_STACK="${STACK_NAME_BACKEND:-${PROJECT_NAME}-backend}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

for tool in aws python3; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "no usable AWS credentials - set AWS_PROFILE or the AWS_* keys in .env"
log "account ${ACCOUNT_ID} in ${AWS_REGION}"

# --- what the backend already has -------------------------------------------

aws cloudformation describe-stacks --stack-name "${BACKEND_STACK}" >/dev/null 2>&1 \
  || die "stack ${BACKEND_STACK} does not exist - run make deploy-backend first"

backend_param() {
  aws cloudformation describe-stacks --stack-name "${BACKEND_STACK}" \
    --query "Stacks[0].Parameters[?ParameterKey=='$1'].ParameterValue" --output text
}
backend_output() {
  aws cloudformation describe-stacks --stack-name "${BACKEND_STACK}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

VPC_ID="$(backend_param VpcId)"
SUBNET_IDS="$(backend_param SubnetIds)"
SECURITY_GROUP="$(aws cloudformation describe-stack-resource --stack-name "${BACKEND_STACK}" \
  --logical-resource-id FunctionSecurityGroup \
  --query StackResourceDetail.PhysicalResourceId --output text)"
BACKEND_FUNCTION="$(backend_output FunctionName)"

# The builder must query the schema the API migrated to, so both run the same
# image; deploy-backend.sh moves the report functions along on every deploy.
IMAGE_URI="${REPORTS_IMAGE_URI:-$(aws lambda get-function --function-name "${BACKEND_FUNCTION}" \
  --query Code.ImageUri --output text)}"
ARCHITECTURE="$(aws lambda get-function-configuration --function-name "${BACKEND_FUNCTION}" \
  --query 'Architectures[0]' --output text)"
DATABASE_URL="$(aws secretsmanager get-secret-value \
  --secret-id "$(backend_output DatabaseUrlSecretArn)" --query SecretString --output text)"

# The gateway endpoint goes on the route table each subnet actually uses: its
# own if it has an explicit association, the VPC's main table otherwise.
ROUTE_TABLE_IDS="$(python3 -c '
import json, subprocess, sys
vpc, subnets = sys.argv[1], sys.argv[2].split(",")
tables = json.loads(subprocess.check_output([
    "aws", "ec2", "describe-route-tables", "--output", "json",
    "--filters", "Name=vpc-id,Values=" + vpc,
]))["RouteTables"]
main = next(t["RouteTableId"] for t in tables for a in t.get("Associations", []) if a.get("Main"))
explicit = {a["SubnetId"]: t["RouteTableId"]
            for t in tables for a in t.get("Associations", []) if a.get("SubnetId")}
print(",".join(sorted({explicit.get(s, main) for s in subnets})))
' "${VPC_ID}" "${SUBNET_IDS}")"

log "image ${IMAGE_URI##*/} (${ARCHITECTURE}), vpc ${VPC_ID}, route tables ${ROUTE_TABLE_IDS}"

# --- deploy -----------------------------------------------------------------

# Through a 0600 file rather than argv: the database URL carries the password.
PARAMS_FILE="$(mktemp)"
chmod 600 "${PARAMS_FILE}"
trap 'rm -f "${PARAMS_FILE}"' EXIT

PROJECT_NAME="${PROJECT_NAME}" \
IMAGE_URI="${IMAGE_URI}" \
ARCHITECTURE="${ARCHITECTURE}" \
VPC_ID="${VPC_ID}" \
SUBNET_IDS="${SUBNET_IDS}" \
ROUTE_TABLE_IDS="${ROUTE_TABLE_IDS}" \
SECURITY_GROUP="${SECURITY_GROUP}" \
DATABASE_URL="${DATABASE_URL}" \
MAIL_DOMAIN="${REPORTS_MAIL_DOMAIN:-}" \
RECIPIENTS="${REPORT_RECIPIENTS:-}" \
SCHEDULE="${REPORTS_SCHEDULE:-cron(0 7 ? * MON *)}" \
FAIL_WEEK="${REPORTS_FAIL_WEEK:-}" \
python3 - "${PARAMS_FILE}" <<'PY'
import json, os, sys

env = os.environ
params = {
    "ProjectName": env["PROJECT_NAME"],
    "ImageUri": env["IMAGE_URI"],
    "Architecture": env["ARCHITECTURE"],
    "VpcId": env["VPC_ID"],
    "SubnetIds": env["SUBNET_IDS"],
    "RouteTableIds": env["ROUTE_TABLE_IDS"],
    "FunctionSecurityGroupId": env["SECURITY_GROUP"],
    "DatabaseUrl": env["DATABASE_URL"],
    "MailDomain": env["MAIL_DOMAIN"],
    "Recipients": env["RECIPIENTS"],
}
# Empty means "keep the stack's value" (or the template default on a new
# stack): a deploy without .env must not drop the domain or the recipients.
chosen = [{"ParameterKey": k, "ParameterValue": v} for k, v in params.items() if v != ""]
# These two are always sent, so a plain re-deploy puts them back to normal.
chosen += [
    {"ParameterKey": "ScheduleExpression", "ParameterValue": env["SCHEDULE"]},
    {"ParameterKey": "FailWeek", "ParameterValue": env["FAIL_WEEK"]},
]
json.dump(chosen, open(sys.argv[1], "w"))
PY

[[ -z "${REPORTS_FAIL_WEEK:-}" ]] || warn "the builder will fail ${REPORTS_FAIL_WEEK} on purpose"
[[ "${REPORTS_SCHEDULE:-}" == "" ]] || warn "schedule set to ${REPORTS_SCHEDULE} - re-deploy without it to go back to Mondays"

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

# --- ses --------------------------------------------------------------------

MAIL_DOMAIN="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Parameters[?ParameterKey=='MailDomain'].ParameterValue" --output text)"
RECIPIENTS="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Parameters[?ParameterKey=='Recipients'].ParameterValue" --output text)"

if [[ -n "${MAIL_DOMAIN}" && "${MAIL_DOMAIN}" != "None" ]]; then
  DKIM_STATUS="$(aws sesv2 get-email-identity --email-identity "${MAIL_DOMAIN}" \
    --query DkimAttributes.Status --output text)"
  log "SES identity ${MAIL_DOMAIN}: DKIM ${DKIM_STATUS}"
  if [[ "${DKIM_STATUS}" != "SUCCESS" ]]; then
    echo "  Add these three CNAME records at the DNS provider (Namecheap: Host is the"
    echo "  name without .${MAIL_DOMAIN}); SES checks them on its own within minutes."
    for n in 1 2 3; do
      read -r name value <<<"$(output "Dkim${n}")"
      printf '    %-60s CNAME  %s\n' "${name}" "${value}"
    done
  fi
else
  warn "REPORTS_MAIL_DOMAIN unset - the mailer logs reports instead of sending them"
fi

# A sandboxed account delivers only to verified addresses. Asking SES to
# verify one sends it a link; nothing is sent to addresses already verified.
SANDBOX="$(aws sesv2 get-account --query 'ProductionAccessEnabled' --output text)"
if [[ "${SANDBOX}" != "True" && -n "${RECIPIENTS}" && "${RECIPIENTS}" != "None" ]]; then
  IFS=',' read -r -a addresses <<<"${RECIPIENTS}"
  for address in "${addresses[@]}"; do
    address="${address// /}"
    [[ -n "${address}" ]] || continue
    if aws sesv2 get-email-identity --email-identity "${address}" >/dev/null 2>&1; then
      status="$(aws sesv2 get-email-identity --email-identity "${address}" \
        --query VerifiedForSendingStatus --output text)"
      [[ "${status}" == "True" ]] \
        || warn "${address} has not clicked the SES verification link yet"
    else
      aws sesv2 create-email-identity --email-identity "${address}" >/dev/null
      log "SES sandbox: sent a verification link to ${address} - open it before the first report"
    fi
  done
fi

# --- report -----------------------------------------------------------------

echo
echo "  bucket     s3://$(output BucketName)/reports/"
echo "  queue      $(output QueueUrl)"
echo "  dlq        $(output DeadLetterQueueUrl)"
echo "  schedule   $(output ScheduleName) (${REPORTS_SCHEDULE:-cron(0 7 ? * MON *)}, Europe/Kyiv)"
echo "  logs       make report-logs"
echo
echo "Next: make report-now WEEK=<an ISO week, e.g. 2026-W41>, then make report-ls."
