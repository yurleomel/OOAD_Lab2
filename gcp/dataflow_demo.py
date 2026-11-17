#!/usr/bin/env python3
"""Run one bounded three-row Dataflow batch demo; retain all artifacts/data."""

import json
import shutil
import subprocess
import time
import uuid
from urllib.parse import urlencode

from demos import PROJECT, google_api, record
from deploy import ROOT


def verify_output(output_table):
    table_id = output_table.rsplit(".", 1)[1]
    base = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/datasets/lab9/tables/"
    table = google_api(base + table_id, method="GET")
    data = google_api(base + table_id + "/data?maxResults=10", method="GET")
    fields = [field["name"] for field in table["schema"]["fields"]]
    rows = [
        dict(zip(fields, [cell["v"] for cell in row["f"]], strict=True))
        for row in data.get("rows", [])
    ]
    if len(rows) != 3 or {int(row["id"]) for row in rows} != {1, 2, 3}:
        raise RuntimeError("Expected exactly the three synthetic output rows")
    if sum(int(row["minutes"]) for row in rows) != 30:
        raise RuntimeError("Dataflow output does not preserve the 30-minute total")
    return rows


def main():
    gcloud = shutil.which("gcloud") or str(ROOT / ".gcp-builds/tools/google-cloud-sdk/bin/gcloud")
    suffix = uuid.uuid4().hex[:12]
    prefix = f"gs://{PROJECT}-lab9/dataflow-{suffix}"
    for filename in ("input.csv", "transform.js", "schema.json"):
        subprocess.run(
            [
                gcloud,
                "storage",
                "cp",
                "--no-clobber",
                str(ROOT / "labs/lab9/dataflow" / filename),
                prefix + "/" + filename,
            ],
            check=True,
        )
    template = "gs://dataflow-templates-us-central1/latest/GCS_Text_to_BigQuery"
    output_table = f"{PROJECT}:lab9.dataflow_demo_{suffix}"
    # A unique output table is mandatory: never point a template at existing data.
    launch = {
        "jobName": "peach-lab9-" + suffix,
        "parameters": {
            "inputFilePattern": prefix + "/input.csv",
            "JSONPath": prefix + "/schema.json",
            "outputTable": output_table,
            "javascriptTextTransformGcsPath": prefix + "/transform.js",
            "javascriptTextTransformFunctionName": "transform",
            "bigQueryLoadingTemporaryDirectory": prefix + "/bq-temp",
        },
        "environment": {
            "numWorkers": 1,
            "maxWorkers": 1,
            "machineType": "e2-standard-2",
            "diskSizeGb": 30,
            "serviceAccountEmail": f"peach-dataflow@{PROJECT}.iam.gserviceaccount.com",
            "tempLocation": prefix + "/temp",
            "workerRegion": "us-central1",
            "additionalUserLabels": {"lab": "9", "purpose": "three-synthetic-rows"},
        },
    }
    base = f"https://dataflow.googleapis.com/v1b3/projects/{PROJECT}/locations/us-central1"
    parameters = {"gcsPath": template, "validateOnly": "true"}
    google_api(base + "/templates:launch?" + urlencode(parameters), launch)
    parameters["validateOnly"] = "false"
    job = google_api(base + "/templates:launch?" + urlencode(parameters), launch)["job"]
    job_id = job["id"]
    print("Launched one worker, 3 input rows. Job:", job_id, flush=True)
    print("Output table:", output_table, flush=True)
    print(json.dumps({"workers": 1, "max_minutes": 12, "input_prefix": prefix}), flush=True)
    manifest = {
        "project": PROJECT,
        "job_id": job_id,
        "region": "us-central1",
        "template": template,
        "input_rows": 3,
        "output_table": output_table,
        "launch": launch,
    }
    # Save the job ID immediately so it can be audited/stopped independently.
    record("dataflow-launch", manifest.copy())
    deadline = time.monotonic() + 12 * 60
    terminal = {"JOB_STATE_DONE", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_DRAINED"}
    previous = None
    while time.monotonic() < deadline:
        job = google_api(base + "/jobs/" + job_id, method="GET")
        state = job["currentState"]
        if state != previous:
            print("Dataflow state:", state, flush=True)
            previous = state
        if state in terminal:
            manifest.update(
                state=state,
                create_time=job.get("createTime"),
                current_state_time=job.get("currentStateTime"),
            )
            if state == "JOB_STATE_DONE":
                manifest["output_rows"] = verify_output(output_table)
            record("dataflow-result", manifest)
            if state != "JOB_STATE_DONE":
                raise RuntimeError("Dataflow demo did not complete: " + state)
            return
        time.sleep(10)
    google_api(base + "/jobs/" + job_id, {"requestedState": "JOB_STATE_CANCELLED"}, method="PUT")
    manifest["state"] = "cancel requested after 12-minute safety timeout"
    record("dataflow-timeout", manifest)
    raise RuntimeError("Stopped the bounded demo after the safety timeout; outputs retained")


if __name__ == "__main__":
    main()
