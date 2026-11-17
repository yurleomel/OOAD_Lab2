"""Publish a retained static export through the Firebase Hosting REST API.

Uses the already authorized gcloud identity's short-lived token, not a JSON
service-account key. Prior versions and local artifacts are retained.
"""

import gzip
import hashlib
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Refusing to redirect an authenticated Hosting API request")


def publish(build_dir: Path, project: str) -> None:
    root = Path(__file__).resolve().parent.parent
    gcloud = shutil.which("gcloud") or str(root / ".gcp-builds/tools/google-cloud-sdk/bin/gcloud")
    token = subprocess.check_output([gcloud, "auth", "print-access-token"], text=True).strip()
    base = "https://firebasehosting.googleapis.com/v1beta1/"

    def api(path, payload, *, method="POST", binary=False):
        url = path if path.startswith("https://") else base + path
        if (
            urlparse(url).hostname
            not in {"firebasehosting.googleapis.com", "upload-firebasehosting.googleapis.com"}
            or urlparse(url).scheme != "https"
        ):
            raise ValueError("Unexpected Hosting API upload destination")
        data = payload if binary else json.dumps(payload).encode()
        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/octet-stream" if binary else "application/json",
                "X-Goog-User-Project": project,
            },
        )
        try:
            with build_opener(NoRedirects()).open(request, timeout=60) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except HTTPError as error:
            raise RuntimeError("Hosting API failed: " + error.read().decode()[:1500]) from None

    config = json.loads((build_dir / "firebase.json").read_text())["hosting"]
    headers = [
        {
            "glob": rule["source"],
            "headers": {item["key"]: item["value"] for item in rule["headers"]},
        }
        for rule in config["headers"]
    ]
    version = api(
        f"sites/{project}/versions",
        {
            "config": {
                "cleanUrls": True,
                "trailingSlashBehavior": "REMOVE",
                "headers": headers,
            }
        },
    )["name"]
    if not version.startswith(f"sites/{project}/versions/"):
        raise ValueError("Unexpected Hosting version name")
    content = {}
    hashes = {}
    public = build_dir / "frontend/out"
    for path in sorted(public.rglob("*")):
        if path.is_file():
            compressed = gzip.compress(path.read_bytes(), mtime=0)
            digest = hashlib.sha256(compressed).hexdigest()
            hashes["/" + path.relative_to(public).as_posix()] = digest
            content[digest] = compressed

    files = list(hashes.items())
    uploaded = 0
    for offset in range(0, len(files), 1000):
        response = api(version + ":populateFiles", {"files": dict(files[offset : offset + 1000])})
        upload_url = response["uploadUrl"]
        required = response.get("uploadRequiredHashes", [])

        def upload(digest, destination=upload_url):
            api(destination + "/" + digest, content[digest], binary=True)

        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(upload, required))
        uploaded += len(required)
    api(version + "?update_mask=status", {"status": "FINALIZED"}, method="PATCH")
    release = api(f"sites/{project}/releases?" + urlencode({"versionName": version}), {})
    evidence = {
        "version": version,
        "release": release.get("name"),
        "files": len(hashes),
        "uploaded": uploaded,
        "url": f"https://{project}.web.app",
    }
    with (build_dir / "release.json").open("x") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
