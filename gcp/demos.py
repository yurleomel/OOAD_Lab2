#!/usr/bin/env python3
"""Small bounded BigQuery/OCR demonstrations; no load generation or cleanup."""

import argparse
import base64
import json
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener

from deploy import ROOT
from hosting import NoRedirects

PROJECT = "lanora-511019"
MAX_QUERY_BYTES = 104_857_600


def google_api(url, payload=None, *, method="POST"):
    gcloud = shutil.which("gcloud") or str(ROOT / ".gcp-builds/tools/google-cloud-sdk/bin/gcloud")
    token = subprocess.check_output([gcloud, "auth", "print-access-token"], text=True).strip()
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "X-Goog-User-Project": PROJECT,
        },
    )
    try:
        with build_opener(NoRedirects()).open(request, timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError("Demo request failed: " + error.read().decode()[:2000]) from None


def record(kind, value):
    directory = Path(ROOT, "submission/lab9")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{kind}-{uuid.uuid4().hex[:8]}.json"
    # Keep this standalone helper compatible with Python 3.10 as well.
    value["recorded_at"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    with path.open("x") as output:
        json.dump(value, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print(json.dumps(value, indent=2, ensure_ascii=False))
    print("Saved evidence:", path)


def bigquery():
    query = (ROOT / "labs/lab9/bigquery.sql").read_text()
    base = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}"
    configuration = {
        "query": query,
        "useLegacySql": False,
        "maximumBytesBilled": str(MAX_QUERY_BYTES),
    }
    dry_run = google_api(
        base + "/jobs", {"configuration": {"dryRun": True, "query": configuration}}
    )
    processed = int(dry_run["statistics"]["query"]["totalBytesProcessed"])
    if processed > MAX_QUERY_BYTES:
        raise RuntimeError("Query estimate exceeds the 100 MiB safety limit")
    configuration.update(
        destinationTable={
            "projectId": PROJECT,
            "datasetId": "lab9",
            "tableId": "shakespeare_top10",
        },
        writeDisposition="WRITE_EMPTY",
        createDisposition="CREATE_NEVER",
    )
    job_id = "lab9_words_" + uuid.uuid4().hex
    google_api(
        base + "/jobs",
        {
            "configuration": {"query": configuration},
            "jobReference": {"projectId": PROJECT, "jobId": job_id, "location": "US"},
        },
    )
    for _ in range(60):
        job = google_api(base + f"/jobs/{job_id}?location=US", method="GET")
        if job["status"]["state"] == "DONE":
            break
        time.sleep(1)
    else:
        raise RuntimeError("Query did not finish in one minute")
    if "errorResult" in job["status"]:
        raise RuntimeError(str(job["status"]["errorResult"]))
    result = google_api(base + f"/queries/{job_id}?location=US", method="GET")
    fields = [field["name"] for field in result["schema"]["fields"]]
    rows = [
        dict(zip(fields, [cell["v"] for cell in row["f"]], strict=True))
        for row in result.get("rows", [])
    ]
    record(
        "bigquery",
        {
            "project": PROJECT,
            "job_id": job_id,
            "location": "US",
            "sql": query,
            "dry_run_bytes": processed,
            "statistics": job["statistics"]["query"],
            "destination": PROJECT + ".lab9.shakespeare_top10",
            "rows": rows,
        },
    )


def ocr():
    from PIL import Image, ImageDraw, ImageFont

    directory = ROOT / "submission/lab9"
    directory.mkdir(parents=True, exist_ok=True)
    image_path = directory / ("synthetic-receipt-" + uuid.uuid4().hex[:8] + ".png")
    image = Image.new("RGB", (1000, 720), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 30)
    receipt = (ROOT / "labs/lab9/receipt.txt").read_text()
    draw.multiline_text((60, 50), receipt, font=font, fill="black", spacing=16)
    image.save(image_path)
    response = google_api(
        "https://vision.googleapis.com/v1/images:annotate",
        {
            "requests": [
                {
                    "image": {"content": base64.b64encode(image_path.read_bytes()).decode()},
                    "features": [{"type": "TEXT_DETECTION", "maxResults": 1}],
                }
            ]
        },
    )
    result = response["responses"][0]
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    text = result.get("fullTextAnnotation", {}).get("text", "")
    if "3.50" not in text or "LANORA" not in text:
        raise RuntimeError("Expected synthetic receipt text was not recognized")
    record(
        "vision-ocr",
        {
            "project": PROJECT,
            "service": "Vision API TEXT_DETECTION",
            "input": image_path.name,
            "text": text,
            "response": response,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", choices=["bigquery", "ocr"])
    args = parser.parse_args()
    {"bigquery": bigquery, "ocr": ocr}[args.demo]()
