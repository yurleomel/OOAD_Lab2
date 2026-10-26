#!/usr/bin/env bash
# Day-to-day commands for the deployed weekly report (infra/reports.tf).
#
#   report.sh now [WEEK]   queue a report; no week means the last complete one
#   report.sh ls           the reports in the bucket
#   report.sh logs         the trigger lines from both functions (SINCE_HOURS, default 24)
#   report.sh status       messages waiting in the queue and the dead-letter queue
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

if [[ -f "${ROOT}/.env" ]]; then
  preset="$(export -p)"
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
  eval "${preset}"
fi
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
export AWS_DEFAULT_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"

# The queue and bucket names come from the Terraform state (infra/outputs.tf).
output() {
  terraform -chdir="${ROOT}/infra" output -raw "$1" 2>/dev/null \
    || die "no Terraform output $1 - run terraform login and make infra-init first"
}

case "${1:-}" in
  now)
    week="${2:-}"
    if [[ -n "${week}" ]]; then
      [[ "${week}" =~ ^[0-9]{4}-W[0-9]{2}$ ]] || die "WEEK must look like 2026-W41, got '${week}'"
      body="{\"week\": \"${week}\", \"source\": \"make\"}"
    else
      body='{"week": null, "source": "make"}'
    fi
    id="$(aws sqs send-message --queue-url "$(output report_queue_url)" --message-body "${body}" \
      --query MessageId --output text)"
    echo "queued ${body} as message ${id}"
    ;;
  ls)
    aws s3 ls "s3://$(output reports_bucket)/reports/" --recursive
    ;;
  logs)
    since=$(( ($(date +%s) - ${SINCE_HOURS:-24} * 3600) * 1000 ))
    for fn in builder mailer; do
      aws logs filter-log-events \
        --log-group-name "/aws/lambda/${PROJECT_NAME}-report-${fn}" \
        --start-time "${since}" \
        --filter-pattern '"triggered"' \
        --output json \
        | python3 -c 'import json, sys
for e in json.load(sys.stdin)["events"]:
    print(e["message"].rstrip())'
    done
    ;;
  status)
    for name in report_queue_url report_dlq_url; do
      url="$(output "${name}")"
      aws sqs get-queue-attributes --queue-url "${url}" \
        --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
        --query "Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]" \
        --output text | awk -v q="${url##*/}" '{printf "%-36s waiting %s, in flight %s\n", q, $1, $2}'
    done
    ;;
  *)
    sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
