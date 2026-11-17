#!/usr/bin/env python3
"""Explain each line in the four local estimates, without contacting a cloud."""

import json
from decimal import Decimal as D

from costs import MONTH_HOURS, PROFILES, estimate


def breakdown(hours):
    summary = estimate(hours)
    requests = D(summary["requests"])
    aws = {
        "rds_instance": MONTH_HOURS * D("0.016"),
        "rds_20_gib_gp2": D(20) * D("0.115"),
        "rds_backup_within_included_allocation": D(0),
        "lambda_compute_and_requests": D(summary["aws_api"]),
        "s3_static_storage_and_origin_gets": D("0.003") * D("0.023")
        + D(10_000) / 1000 * D("0.0004"),
        "cloudfront_delivery_within_shared_free_quota": D(0),
        "ecr_assumed_half_gb_retained": D("0.5") * D("0.10"),
        "database_secret": D("0.40"),
        "cloudwatch_within_shared_free_quota": D(0),
        "cognito_within_existing_shared_free_quota": D(0),
        "tls_certificate_and_existing_dns": D(0),
    }

    def google(active_hours):
        return {
            "cloud_sql_compute": active_hours * D("0.0105"),
            "cloud_sql_idle_ipv4": (MONTH_HOURS - active_hours) * D("0.01"),
            "cloud_sql_10_gib_ssd": D(10) * D("0.17"),
            "cloud_sql_assumed_1_gib_used_backup": D("0.08"),
            "cloud_run_compute_and_requests": D(summary["gcp_api"]),
            "api_egress_to_europe": D(summary["gcp_egress"]),
            "firebase_hosting_within_daily_transfer_and_storage_quotas": D(0),
            "artifact_registry_within_shared_half_gib_quota": D(0),
            "secret_manager_within_shared_version_and_access_quotas": D(0),
            "cloud_logging_within_free_quota": D(0),
            "tls_certificate_and_firebase_default_domain": D(0),
        }

    always_running = google(MONTH_HOURS)
    stopped_between_demos = google(hours)
    assert sum(aws.values()) == D(summary["aws_total"])
    assert sum(always_running.values()) == D(summary["gcp_always_running_total"])
    assert sum(stopped_between_demos.values()) == D(summary["gcp_scheduled_total"])
    return {
        "inputs": {
            "active_hours": str(hours),
            "requests": str(requests),
            "requests_per_active_second": 1,
            "assumed_billed_duration_ms": 200,
            "memory_gib": "0.5",
            "cloud_run_vcpu": 1,
            "simultaneous_requests_assumed": 1,
            "configured_cloud_run_concurrency_limit": 10,
            "response_bytes": 2048,
            "response_destination": "Europe",
            "total_api_response_gib": str(requests * 2048 / (1024**3)),
            "static_origin_gets_per_month": 10_000,
            "static_transfer_assumption": "Small cached site; below Firebase 360 MB each day",
        },
        "aws_components_usd": {key: str(value) for key, value in aws.items()},
        "gcp_always_running_components_usd": {
            key: str(value) for key, value in always_running.items()
        },
        "gcp_scheduled_components_usd": {
            key: str(value) for key, value in stopped_between_demos.items()
        },
        "totals_usd": summary,
    }


def report():
    return {
        "as_of": "2026-11-17",
        "currency": "USD",
        "month_hours": str(MONTH_HOURS),
        "type": "Arithmetic forecast; neither a measured bill nor a load test",
        "calculator_ui_verification": "Pending; no calculator result is claimed by this file",
        "free_tier_assumption": "Shared monthly/daily allowances remain available",
        "excluded": [
            "Promotional credits and tax",
            "Optional report, email, AI and one-off data-platform demo workloads",
            "External domain registrar renewal",
            "Unexpected bursts, extra images, log retention and cold-start overhead",
        ],
        "sources": {
            "cloud_sql": "https://cloud.google.com/sql/pricing",
            "cloud_run": "https://cloud.google.com/run/pricing",
            "firebase_hosting": "https://firebase.google.com/pricing",
            "artifact_registry": "https://cloud.google.com/artifact-registry/pricing",
            "secret_manager": "https://cloud.google.com/secret-manager/pricing",
            "cloud_logging": "https://cloud.google.com/products/observability/pricing",
            "aws_rds": "https://aws.amazon.com/rds/postgresql/pricing/",
            "aws_lambda": "https://aws.amazon.com/lambda/pricing/",
            "aws_cloudfront": "https://aws.amazon.com/cloudfront/faqs/",
        },
        "profiles": {name: breakdown(hours) for name, hours in PROFILES.items()},
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
