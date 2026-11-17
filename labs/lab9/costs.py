#!/usr/bin/env python3
"""A local cost model, never a load test or cloud provisioning command.

Rates checked 2026-11-17. These assumptions are estimates, not measured API
latency or the bill. Calculator verification is recorded separately.
"""

import json
from decimal import Decimal as D

MONTH_HOURS = D(730)
PROFILES = {"nobody": D(0), "class demos": D(20), "office hours": D(176), "always busy": D(730)}


def estimate(hours):
    requests = hours * 3600  # assumed 1 request/second during the profile
    active_seconds = requests * D("0.2")  # assumed billed duration, not benchmarked
    gib_seconds = active_seconds * D("0.5")
    gib_out = requests * 2048 / (1024 ** 3)  # assumed 2 KiB responses to Europe
    aws_api = max(requests - 1_000_000, 0) * D("0.0000002")
    aws_api += max(gib_seconds - 400_000, 0) * D("0.0000133334")
    gcp_api = max(requests - 2_000_000, 0) * D("0.0000004")
    gcp_api += max(active_seconds - 180_000, 0) * D("0.000024")
    gcp_api += max(gib_seconds - 360_000, 0) * D("0.0000025")

    # Actual AWS RDS class/storage, one secret, 0.5 GB private registry,
    # 3 MB S3 site and 10k S3 origin GETs/month. Logs/CDN within shared quotas.
    aws_fixed = MONTH_HOURS * D("0.016") + 20 * D("0.115")
    aws_fixed += D("0.40") + D("0.5") * D("0.10")
    aws_fixed += D("0.003") * D("0.023") + D(10_000) / 1000 * D("0.0004")
    # 10 GB SSD and assumed 1 GiB used backup storage on GCP.
    gcp_retained = 10 * D("0.17") + D("0.08")
    gcp_running = MONTH_HOURS * D("0.0105") + gcp_retained
    # Public IPv4 is billable when the instance is stopped.
    gcp_scheduled = hours * D("0.0105") + (MONTH_HOURS - hours) * D("0.01") + gcp_retained
    gcp_egress = gib_out * D("0.12")  # do not claim North America-only free egress for Europe
    return {
        "hours": str(hours), "requests": str(requests),
        "aws_api": str(aws_api), "gcp_api": str(gcp_api),
        "gcp_egress": str(gcp_egress),
        "aws_total": str(aws_fixed + aws_api),
        "gcp_always_running_total": str(gcp_running + gcp_api + gcp_egress),
        "gcp_scheduled_total": str(gcp_scheduled + gcp_api + gcp_egress),
    }


if __name__ == "__main__":
    print(json.dumps({name: estimate(hours) for name, hours in PROFILES.items()}, indent=2))
