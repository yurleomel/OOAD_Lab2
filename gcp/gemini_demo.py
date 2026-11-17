#!/usr/bin/env python3
"""One small Vertex AI Gemini agenda call with Lab 6's real prompt/schema."""

import json
import subprocess
import uuid

from demos import PROJECT, google_api, record
from deploy import ROOT


def main():
    sample = (ROOT / "labs/lab9/agenda.txt").read_text().strip()
    export = """
import json,sys
from datetime import date
from app.ai.agenda import SYSTEM,RECORD_AGENDA,PROMPT_VERSION,_today_line
sample=sys.stdin.read()
prompt=_today_line(date(2026,10,20),'Europe/Kyiv')+'\\n\\n<pasted_text>\\n'+sample+'\\n</pasted_text>'
print(json.dumps({'system':SYSTEM,'tool':RECORD_AGENDA,'prompt':prompt,'prompt_version':PROMPT_VERSION}))
"""
    result = subprocess.run(
        [
            "docker",
            "run",
            "-i",
            "--platform",
            "linux/amd64",
            "--name",
            "peach-gcp-prompt-" + uuid.uuid4().hex[:8],
            "peach-gcp:lab9",
            "python",
            "-c",
            export,
        ],
        input=sample,
        text=True,
        capture_output=True,
        check=True,
    )
    fixture = json.loads(result.stdout)
    model = "gemini-3.8-flash"
    body = {
        "systemInstruction": {"parts": [{"text": fixture["system"]}]},
        "contents": [{"role": "user", "parts": [{"text": fixture["prompt"]}]}],
        "tools": [
            {
                "functionDeclarations": [
                    {
                        "name": fixture["tool"]["name"],
                        "description": fixture["tool"]["description"],
                        "parametersJsonSchema": fixture["tool"]["input_schema"],
                    }
                ]
            }
        ],
        "toolConfig": {
            "functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": ["record_agenda"]}
        },
        "generationConfig": {"maxOutputTokens": 1024, "thinkingConfig": {"thinkingLevel": "LOW"}},
    }
    endpoint = f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/global/publishers/google/models/{model}:generateContent"
    response = google_api(endpoint, body)
    calls = [
        part["functionCall"]
        for candidate in response.get("candidates", [])
        for part in candidate.get("content", {}).get("parts", [])
        if "functionCall" in part
    ]
    if len(calls) != 1 or calls[0]["name"] != "record_agenda":
        record("gemini-incomplete", {"model": model, "response": response})
        raise RuntimeError("Expected exactly one agenda tool call; no automatic paid retry")
    agenda = calls[0]["args"]
    validate = """
import json,sys
from app.schemas.agenda import ParsedAgenda
agenda=ParsedAgenda.model_validate(json.load(sys.stdin))
print(agenda.model_dump_json())
"""
    validation = subprocess.run(
        [
            "docker",
            "run",
            "-i",
            "--platform",
            "linux/amd64",
            "--name",
            "peach-gcp-gemini-validate-" + uuid.uuid4().hex[:8],
            "peach-gcp:lab9",
            "python",
            "-c",
            validate,
        ],
        input=json.dumps(agenda),
        text=True,
        capture_output=True,
        check=True,
    )
    record(
        "gemini-agenda",
        {
            "project": PROJECT,
            "model": model,
            "endpoint_region": "global",
            "reference_date": "2026-10-20",
            "input": sample,
            "fixture": fixture,
            "agenda": json.loads(validation.stdout),
            "usage": response.get("usageMetadata"),
            "model_version": response.get("modelVersion"),
            "response": response,
        },
    )


if __name__ == "__main__":
    main()
