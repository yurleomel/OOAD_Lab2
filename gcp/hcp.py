#!/usr/bin/env python3
"""Set deployment inputs on peach-gcp only; never changes the AWS workspace."""

import argparse
import json
from pathlib import Path
from urllib.request import Request, build_opener

from hosting import NoRedirects

BASE = "https://app.terraform.io/api/v2/"


def set_input(key: str, value: str) -> None:
    token_path = Path.home() / ".terraform.d/credentials.tfrc.json"
    token = json.loads(token_path.read_text())["credentials"]["app.terraform.io"]["token"]

    def api(path, payload=None, method="GET"):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            BASE + path,
            data=data,
            method=method,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/vnd.api+json",
            },
        )
        with build_opener(NoRedirects()).open(request, timeout=30) as response:
            return json.load(response)

    workspace = api("organizations/ooad-yurleomel/workspaces/peach-gcp")["data"]["id"]
    variables = api(f"workspaces/{workspace}/vars")["data"]
    existing = next(
        (
            item
            for item in variables
            if item["attributes"]["key"] == key and item["attributes"]["category"] == "terraform"
        ),
        None,
    )
    attributes = {
        "key": key,
        "value": value,
        "category": "terraform",
        "sensitive": False,
        "hcl": key == "database_running",
    }
    payload = {"data": {"type": "vars", "attributes": attributes}}
    if existing:
        api(f"workspaces/{workspace}/vars/{existing['id']}", payload, "PATCH")
    else:
        api(f"workspaces/{workspace}/vars", payload, "POST")
    print(f"Set {key} on peach-gcp. A reviewed Terraform plan/apply is still required.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", choices=["api_image", "database_running"])
    parser.add_argument("value")
    args = parser.parse_args()
    if args.key == "database_running" and args.value not in {"true", "false"}:
        parser.error("database_running must be true or false")
    set_input(args.key, args.value)
