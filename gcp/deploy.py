#!/usr/bin/env python3
"""GCP build helpers. Build artifacts are retained; no cleanup/delete commands."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
FIREBASE_VERSION = "15.36.0"


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, **kwargs)


def public_auth_config() -> dict[str, str]:
    """Read only public Cognito build settings; never source or copy .env."""
    keys = {
        "COGNITO_REGION",
        "COGNITO_USER_POOL_ID",
        "COGNITO_CLIENT_ID",
        "COGNITO_DOMAIN",
    }
    values = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in keys:
                values[key.strip()] = value.strip().strip("\"'")
    for key in keys:
        if key in os.environ:
            values[key] = os.environ[key]
    missing = keys - values.keys()
    if missing or any(not value for value in values.values()):
        raise ValueError("Set the existing public COGNITO_* settings in .env first")
    return values


def package_manager() -> list[str]:
    pin = json.loads((ROOT / "frontend/package.json").read_text())["packageManager"]
    if shutil.which("corepack"):
        return ["corepack", "pnpm"]
    return ["npx", "--yes", pin]


def firebase_config(site: str) -> dict:
    return {
        "hosting": {
            "site": site,
            "public": "frontend/out",
            "cleanUrls": True,
            "trailingSlash": False,
            "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
            "headers": [
                {
                    "source": "**",
                    "headers": [
                        {"key": "Cache-Control", "value": "public,max-age=0,must-revalidate"}
                    ],
                },
                {
                    "source": "/_next/static/**",
                    "headers": [
                        {"key": "Cache-Control", "value": "public,max-age=31536000,immutable"}
                    ],
                },
                {
                    "source": "**/*.html",
                    "headers": [
                        {"key": "Cache-Control", "value": "public,max-age=0,must-revalidate"}
                    ],
                },
            ],
        }
    }


def build_frontend(args: argparse.Namespace) -> None:
    url = urlparse(args.api_url)
    if url.scheme != "https" or not url.netloc or url.username or url.password:
        raise ValueError("--api-url must be the HTTPS Cloud Run URL without credentials")
    auth = public_auth_config()
    build_root = ROOT / ".gcp-builds"
    build_root.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="frontend-", dir=build_root))
    files = (
        run(["git", "ls-files", "-z", "--", "frontend"], cwd=ROOT, capture_output=True)
        .stdout.decode()
        .split("\0")
    )
    for filename in filter(None, files):
        source = ROOT / filename
        if source.name.startswith(".env"):
            raise ValueError("Refusing to copy an environment file into the frontend build")
        target = destination / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    env = os.environ.copy()
    env.update(
        NODE_ENV="production",
        NEXT_OUTPUT="export",
        NEXT_PUBLIC_API_URL=args.api_url.rstrip("/"),
        NEXT_PUBLIC_COGNITO_REGION=auth["COGNITO_REGION"],
        NEXT_PUBLIC_COGNITO_USER_POOL_ID=auth["COGNITO_USER_POOL_ID"],
        NEXT_PUBLIC_COGNITO_CLIENT_ID=auth["COGNITO_CLIENT_ID"],
        NEXT_PUBLIC_COGNITO_DOMAIN=auth["COGNITO_DOMAIN"],
        # Email/password works with the existing Cognito app client. Google
        # needs the Firebase callback URLs added in AWS before enabling it.
        NEXT_PUBLIC_COGNITO_GOOGLE_ENABLED="false",
        NEXT_PUBLIC_COGNITO_HOSTED_REDIRECTS_ENABLED="false",
        NEXT_PUBLIC_PARSER_URL="",
        COREPACK_ENABLE_DOWNLOAD_PROMPT="0",
    )
    manager = package_manager()
    print(f"Retained build directory: {destination}", flush=True)
    run([*manager, "install", "--frozen-lockfile"], cwd=destination / "frontend", env=env)
    run([*manager, "build"], cwd=destination / "frontend", env=env)
    if not (destination / "frontend/out/index.html").is_file():
        raise ValueError("The static export did not produce index.html")
    (destination / "firebase.json").write_text(
        json.dumps(firebase_config(args.project), indent=2) + "\n"
    )
    (destination / "build.json").write_text(
        json.dumps({"project": args.project, "api_url": args.api_url}, indent=2) + "\n"
    )
    print(f"Static export ready: {destination / 'frontend/out'}")
    print(f"Publish: python3 gcp/deploy.py publish-frontend --build-dir {destination}")


def publish_frontend(args: argparse.Namespace) -> None:
    build_dir = args.build_dir.resolve()
    if not build_dir.is_relative_to((ROOT / ".gcp-builds").resolve()):
        raise ValueError("Publish only a retained .gcp-builds/ artifact")
    metadata = json.loads((build_dir / "build.json").read_text())
    expected_api = run(
        ["terraform", "-chdir=" + str(ROOT / "gcp"), "output", "-raw", "api_url"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if metadata["api_url"].rstrip("/") != expected_api.rstrip("/"):
        raise ValueError(
            "Artifact API URL differs from the deployed Terraform output; rebuild first"
        )
    if args.rest:
        from hosting import publish

        publish(build_dir, metadata["project"])
        return
    run(
        [
            "npx",
            "--yes",
            f"firebase-tools@{FIREBASE_VERSION}",
            "deploy",
            "--only",
            "hosting",
            "--project",
            metadata["project"],
            "--config",
            str(build_dir / "firebase.json"),
        ],
        cwd=build_dir,
    )


def build_image(args: argparse.Namespace) -> None:
    revision = (
        run(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, capture_output=True)
        .stdout.decode()
        .strip()
    )
    # A unique suffix makes an uncommitted working-tree build distinguishable.
    import uuid

    repository = f"{args.region}-docker.pkg.dev/{args.project}/peach/backend"
    tag = f"{repository}:{revision}-{uuid.uuid4().hex[:8]}"
    run(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "--build-context",
            f"cloud-runtime={ROOT / 'gcp/runtime'}",
            "-f",
            str(ROOT / "gcp/Dockerfile"),
            "-t",
            tag,
            str(ROOT / "backend"),
        ]
    )
    if args.push:
        gcloud = shutil.which("gcloud") or str(
            ROOT / ".gcp-builds/tools/google-cloud-sdk/bin/gcloud"
        )
        run([gcloud, "auth", "configure-docker", f"{args.region}-docker.pkg.dev", "--quiet"])
        run(["docker", "push", tag])
        run(
            [
                gcloud,
                "artifacts",
                "docker",
                "images",
                "describe",
                tag,
                "--project",
                args.project,
                "--format=value(image_summary.fully_qualified_digest)",
            ]
        )
    else:
        print(f"Built locally (not pushed): {tag}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    frontend = sub.add_parser("build-frontend")
    frontend.add_argument("--project", required=True)
    frontend.add_argument("--api-url", required=True)
    frontend.set_defaults(handler=build_frontend)
    publish = sub.add_parser("publish-frontend")
    publish.add_argument("--build-dir", type=Path, required=True)
    publish.add_argument(
        "--rest",
        action="store_true",
        help="Use the existing gcloud login through the Hosting REST API",
    )
    publish.set_defaults(handler=publish_frontend)
    image = sub.add_parser("build-image")
    image.add_argument("--project", required=True)
    image.add_argument("--region", default="us-central1")
    image.add_argument("--push", action="store_true")
    image.set_defaults(handler=build_image)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"GCP build failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
