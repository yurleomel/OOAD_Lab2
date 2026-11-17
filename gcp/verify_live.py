#!/usr/bin/env python3
"""Verify real Cognito authentication and a Cloud SQL-backed API read.

Creates one synthetic Cognito test account only when --create-fixture is
explicitly used, suppressing all notifications. Its credentials remain in an
ignored local 0600 file. Tests preserve the account, task and existing data.
"""

import argparse
import json
import os
import secrets
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener

from deploy import ROOT, public_auth_config
from hosting import NoRedirects


def cognito(action, payload, region):
    private = ROOT / ".gcp-builds/private"
    private.mkdir(parents=True, exist_ok=True)
    descriptor, payload_name = tempfile.mkstemp(
        prefix=f"cognito-{action}-", suffix=".json", dir=private
    )
    with os.fdopen(descriptor, "w") as output:
        json.dump(payload, output)
    result = subprocess.run(
        [
            "aws",
            "cognito-idp",
            action,
            "--region",
            region,
            "--cli-input-json",
            "file://" + payload_name,
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"Cognito {action} failed: {result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-fixture", action="store_true")
    parser.add_argument("--api-url", required=True)
    args = parser.parse_args()
    expected_api = subprocess.check_output(
        ["terraform", "-chdir=" + str(ROOT / "gcp"), "output", "-raw", "api_url"], text=True
    ).strip()
    if args.api_url.rstrip("/") != expected_api.rstrip("/") or not expected_api.startswith(
        "https://"
    ):
        raise SystemExit("Refusing to send a fixture token to anything but the deployed GCP API")
    auth = public_auth_config()
    account_path = Path(ROOT, ".gcp-builds/private/lab9-smoke-account.json")
    if not account_path.exists():
        if not args.create_fixture:
            raise SystemExit("No fixture: use --create-fixture to create a synthetic test identity")
        account_path.parent.mkdir(parents=True, exist_ok=True)
        account = {
            "username": f"lab9-{uuid.uuid4().hex[:12]}@example.invalid",
            "password": secrets.token_urlsafe(32) + "Aa1!",
        }
        cognito(
            "admin-create-user",
            {
                "UserPoolId": auth["COGNITO_USER_POOL_ID"],
                "Username": account["username"],
                "TemporaryPassword": account["password"],
                "MessageAction": "SUPPRESS",
                "UserAttributes": [
                    {"Name": "email", "Value": account["username"]},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "name", "Value": "Lab 9 synthetic test"},
                ],
            },
            auth["COGNITO_REGION"],
        )
        # Persist before the next call so retries never create another account.
        descriptor = os.open(account_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            json.dump(account, output)
    account = json.loads(account_path.read_text())
    if args.create_fixture:
        cognito(
            "admin-set-user-password",
            {
                "UserPoolId": auth["COGNITO_USER_POOL_ID"],
                "Username": account["username"],
                "Password": account["password"],
                "Permanent": True,
            },
            auth["COGNITO_REGION"],
        )
    result = cognito(
        "initiate-auth",
        {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": auth["COGNITO_CLIENT_ID"],
            "AuthParameters": {"USERNAME": account["username"], "PASSWORD": account["password"]},
        },
        auth["COGNITO_REGION"],
    )
    token = result["AuthenticationResult"]["IdToken"]
    api_url = args.api_url.rstrip("/")

    def request(path, *, payload=None, authenticated=True):
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = "Bearer " + token
        data = json.dumps(payload).encode() if payload is not None else None
        with build_opener(NoRedirects()).open(
            Request(api_url + path, data=data, headers=headers), timeout=60
        ) as response:
            return response.status, json.load(response)

    assert request("/health", authenticated=False)[1] == {"status": "ok"}
    assert request("/api/v1/health/ready")[1]["database"] == "ok"
    before = request("/api/v1/items")[1]
    _, task = request(
        "/api/v1/items", payload={"name": "Lab 9 GCP persistence check", "status": "todo"}
    )
    after = request("/api/v1/items")[1]
    assert any(item["id"] == task["id"] for item in after["items"])
    assert request("/api/v1/items/" + task["id"])[1]["id"] == task["id"]
    try:
        request("/api/v1/items", authenticated=False)
    except HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError("The API accepted an anonymous request")
    evidence = {
        "api_url": api_url,
        "cognito_authentication": "passed",
        "database_readiness": "passed",
        "task_persists": True,
        "anonymous_status": 401,
        "before_total": before["total"],
        "after_total": after["total"],
        "task_id": task["id"],
        "account_credentials": "retained locally; not in evidence",
    }
    destination = ROOT / ".gcp-builds" / ("live-check-" + uuid.uuid4().hex[:8] + ".json")
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    print("Saved verification:", destination)


if __name__ == "__main__":
    main()
