#!/usr/bin/env python3
"""Refuse Terraform JSON plans containing any deletion, including replacement."""

import json
import sys


def check(plan: dict) -> list[str]:
    if not isinstance(plan.get("format_version"), str):
        raise ValueError("Expected the JSON document from terraform show -json")
    if plan.get("errored") or plan.get("complete") is False:
        raise ValueError("Refusing an errored or incomplete plan")
    blocked = []
    for resource in plan.get("resource_changes", []):
        if "delete" in resource["change"]["actions"]:
            blocked.append(resource["address"])
    return blocked


def main() -> None:
    try:
        blocked = check(json.load(sys.stdin))
    except (ValueError, KeyError, TypeError) as error:
        print(f"Plan was not accepted: {error}", file=sys.stderr)
        sys.exit(1)
    if blocked:
        print("STOP: deletion/replacement is forbidden:\n" + "\n".join(blocked), file=sys.stderr)
        sys.exit(1)
    print("Plan contains no deletions or replacements.")


if __name__ == "__main__":
    main()
