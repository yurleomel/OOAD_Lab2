#!/usr/bin/env python3
"""Run Terraform with a short-lived token from the already signed-in gcloud CLI.

Bootstrap does not need a service-account JSON key or another Google consent
flow. Remote HCP runs still use their own Workload Identity Federation tokens.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from check_plan import check

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    import json

    args = sys.argv[1:]
    bootstrap = bool(args and args[0] == "--bootstrap")
    if bootstrap:
        args = args[1:]
    if not args or args[0] not in {
        "init",
        "validate",
        "fmt",
        "plan",
        "show",
        "output",
        "apply",
        "providers",
    }:
        raise SystemExit(
            "Usage: python3 gcp/tf.py [--bootstrap] "
            "init|validate|fmt|plan|show|output|apply|providers ..."
        )
    directory = ROOT / "gcp" / "bootstrap" if bootstrap else ROOT / "gcp"
    command = ["terraform", "-chdir=" + str(directory)]
    env = os.environ.copy()
    gcloud = shutil.which("gcloud") or str(ROOT / ".gcp-builds/tools/google-cloud-sdk/bin/gcloud")
    token = subprocess.check_output(
        [gcloud, "auth", "print-access-token"], env=env, text=True
    ).strip()
    env["GOOGLE_OAUTH_ACCESS_TOKEN"] = token
    env["GOOGLE_CLOUD_QUOTA_PROJECT"] = "lanora-511019"
    if args[0] == "apply":
        if len(args) != 2 or not args[1].endswith(".tfplan"):
            raise SystemExit(
                "Only a saved, checked .tfplan can be applied here. "
                "Create and review the plan before applying."
            )
        plan = subprocess.check_output([*command, "show", "-json", args[1]], env=env, text=True)
        blocked = check(json.loads(plan))
        if blocked:
            raise SystemExit("STOP: deletion/replacement is forbidden: " + ", ".join(blocked))
    subprocess.run([*command, *args], check=True, env=env)


if __name__ == "__main__":
    main()
