# shellcheck shell=bash
# Shared by domain-frontend.sh and domain-backend.sh: find the Route 53 zone a
# domain sits in, if any, and get an issued us-east-1 ACM certificate for it.
# Sourced, not run. Expects DOMAIN, PROJECT_NAME and the log/warn/die helpers.

# CloudFront only takes certificates from us-east-1, whatever the stack region.
ACM_REGION=us-east-1

# The zone for app.example.com is example.com: walk the labels and keep the
# longest public zone that the domain actually sits under.
find_hosted_zone() {
  DOMAIN="${DOMAIN}" python3 - <<'PY'
import json, os, subprocess

domain = os.environ["DOMAIN"]
out = subprocess.run(
    ["aws", "route53", "list-hosted-zones", "--output", "json"],
    capture_output=True, text=True,
)
if out.returncode != 0:
    raise SystemExit(0)

best = None
for zone in json.loads(out.stdout).get("HostedZones", []):
    if zone.get("Config", {}).get("PrivateZone"):
        continue
    name = zone["Name"].rstrip(".")
    if domain == name or domain.endswith("." + name):
        if best is None or len(name) > len(best[1]):
            best = (zone["Id"].split("/")[-1], name)

if best:
    print(best[0], best[1])
PY
}

# Sets ZONE_ID and ZONE_NAME, empty when the domain's DNS lives elsewhere.
resolve_hosted_zone() {
  ZONE_ID=""
  ZONE_NAME=""
  read -r ZONE_ID ZONE_NAME <<<"$(find_hosted_zone)" || true
  if [[ -n "${ZONE_ID}" ]]; then
    log "${DOMAIN} sits in the Route 53 zone ${ZONE_NAME} (${ZONE_ID})"
  else
    warn "no Route 53 zone covers ${DOMAIN} - you will add DNS records by hand"
  fi
}

# Sets CERT_ARN to an ISSUED certificate for DOMAIN: reuses one that exists,
# otherwise requests it, publishes (or prints) the validation record, and
# waits for ACM. Dies if validation does not come through.
ensure_certificate() {
  CERT_ARN="$(aws acm list-certificates --region "${ACM_REGION}" \
    --certificate-statuses PENDING_VALIDATION ISSUED \
    --query "CertificateSummaryList[?DomainName=='${DOMAIN}']|[0].CertificateArn" \
    --output text 2>/dev/null || true)"

  if [[ -z "${CERT_ARN}" || "${CERT_ARN}" == "None" ]]; then
    log "requesting an ACM certificate for ${DOMAIN} in ${ACM_REGION}"
    CERT_ARN="$(aws acm request-certificate --region "${ACM_REGION}" \
      --domain-name "${DOMAIN}" \
      --validation-method DNS \
      --key-algorithm RSA_2048 \
      --tags "Key=PROJECT_NAME,Value=${PROJECT_NAME}" \
      --query CertificateArn --output text)"
  else
    log "reusing the certificate already requested for ${DOMAIN}"
  fi

  local status
  status="$(aws acm describe-certificate --region "${ACM_REGION}" --certificate-arn "${CERT_ARN}" \
    --query Certificate.Status --output text)"

  if [[ "${status}" != "ISSUED" ]]; then
    # ACM takes a moment to publish the record it wants to see.
    local record=""
    for _ in $(seq 1 12); do
      record="$(aws acm describe-certificate --region "${ACM_REGION}" --certificate-arn "${CERT_ARN}" \
        --query "Certificate.DomainValidationOptions[0].ResourceRecord.[Name,Type,Value]" \
        --output text 2>/dev/null || true)"
      [[ -n "${record}" && "${record}" != *"None"* ]] && break
      sleep 5
    done
    [[ -n "${record}" && "${record}" != *"None"* ]] \
      || die "ACM did not publish a validation record for ${DOMAIN}"

    local name type value
    read -r name type value <<<"${record}"

    if [[ -n "${ZONE_ID}" ]]; then
      log "adding the validation record to Route 53"
      local change_file
      change_file="$(mktemp)"
      cat >"${change_file}" <<JSON
{"Changes":[{"Action":"UPSERT","ResourceRecordSet":{
  "Name":"${name}","Type":"${type}","TTL":300,
  "ResourceRecords":[{"Value":"${value}"}]}}]}
JSON
      aws route53 change-resource-record-sets \
        --hosted-zone-id "${ZONE_ID}" \
        --change-batch "file://${change_file}" >/dev/null
      rm -f "${change_file}"
    else
      echo
      echo "  Add this record wherever ${DOMAIN} is hosted, then leave this running:"
      echo
      echo "    name   ${name}"
      echo "    type   ${type}"
      echo "    value  ${value}"
      echo
    fi

    log "waiting for ACM to validate ${DOMAIN} (minutes, once DNS propagates)"
    for _ in $(seq 1 120); do
      status="$(aws acm describe-certificate --region "${ACM_REGION}" --certificate-arn "${CERT_ARN}" \
        --query Certificate.Status --output text)"
      case "${status}" in
        ISSUED) break ;;
        PENDING_VALIDATION) printf '.' ; sleep 15 ;;
        *) echo; die "certificate ended up ${status} - see ACM in the console" ;;
      esac
    done
    echo
  fi

  [[ "${status}" == "ISSUED" ]] \
    || die "gave up waiting - DNS is probably not published yet, re-run when it is"
  log "certificate issued"
}

# How to point DOMAIN at a CloudFront name when Route 53 cannot do it for us.
print_routing_record() {
  local target="$1"
  echo
  if [[ "${DOMAIN}" == *.*.* ]]; then
    echo "  Last step - point ${DOMAIN} at CloudFront:"
    echo
    echo "    name   ${DOMAIN}"
    echo "    type   CNAME"
    echo "    value  ${target}"
  else
    echo "  Last step - point ${DOMAIN} at ${target}."
    warn "${DOMAIN} is a zone apex, which cannot be a CNAME. Either move the"
    warn "zone to Route 53 and re-run, or use your provider's ALIAS/ANAME record."
  fi
  echo
}
