#!/usr/bin/env python3
"""Verify the Cloud Run image against a new PostgreSQL over a Unix socket.

Uses synthetic signed identities only. Stops and retains its own containers
and data volume; no existing database, schema, rows or files are removed.
"""

import json
import subprocess
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

IMAGE = "peach-gcp:lab9"


def docker(*args: str) -> str:
    result = subprocess.run(["docker", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def main() -> None:
    prefix = "peach-gcp-verify-" + uuid.uuid4().hex[:8]
    containers = []
    socket = prefix + "-socket"
    fixture_code = """
import json,time,jwt
from cryptography.hazmat.primitives.asymmetric import rsa
key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
jwk=jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(),as_dict=True)
jwk.update(kid='smoke',use='sig',alg='RS256')
result={'jwks':json.dumps({'keys':[jwk]})}
for person in ['alice','bob']:
    result[person]=jwt.encode({'sub':'gcp-smoke-'+person,'email':person+'@example.invalid',
        'name':person,'iss':'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_smoke',
        'aud':'gcp-smoke','token_use':'id','iat':int(time.time()),'exp':int(time.time())+600},
        key,algorithm='RS256',headers={'kid':'smoke'})
print(json.dumps(result))
"""
    try:
        fixture_name = prefix + "-tokens"
        containers.append(fixture_name)
        fixture = json.loads(
            docker(
                "run",
                "--platform",
                "linux/amd64",
                "--name",
                fixture_name,
                IMAGE,
                "python",
                "-c",
                fixture_code,
            )
        )
        pg_name = prefix + "-db"
        containers.append(pg_name)
        docker(
            "run",
            "-d",
            "--name",
            pg_name,
            "-e",
            "POSTGRES_USER=peach",
            "-e",
            "POSTGRES_PASSWORD=smoke-only",
            "-e",
            "POSTGRES_DB=peach",
            "-v",
            socket + ":/var/run/postgresql",
            "postgres:17-alpine",
        )
        for _ in range(40):
            try:
                docker("exec", pg_name, "pg_isready", "-U", "peach", "-d", "peach")
                break
            except subprocess.CalledProcessError:
                time.sleep(0.5)
        else:
            raise RuntimeError("PostgreSQL did not start")

        options = [
            "--platform",
            "linux/amd64",
            "-v",
            socket + ":/cloudsql/smoke",
            "-e",
            "DATABASE_URL=postgresql+asyncpg://peach:smoke-only@/peach?host=/cloudsql/smoke",
            "-e",
            "APP_ENV=production",
            "-e",
            "DB_POOLING=false",
            "-e",
            "PORT=8123",
            "-e",
            "COGNITO_USER_POOL_ID=us-east-1_smoke",
            "-e",
            "COGNITO_CLIENT_ID=gcp-smoke",
            "-e",
            "COGNITO_JWKS=" + fixture["jwks"],
            "-e",
            "CORS_ORIGINS=https://lanora-511019.web.app",
        ]
        migration_name = prefix + "-baseline"
        containers.append(migration_name)
        print(docker("run", "--name", migration_name, *options, IMAGE, "python", "gcp_migrate.py"))

        api_name = prefix + "-api"
        containers.append(api_name)
        docker("run", "-d", "--name", api_name, "-p", "127.0.0.1::8123", *options, IMAGE)
        ports = json.loads(
            docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", api_name)
        )
        base = "http://127.0.0.1:" + ports["8123/tcp"][0]["HostPort"]

        def request(path, *, token=None, payload=None, method="GET"):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            data = json.dumps(payload).encode() if payload is not None else None
            with urlopen(
                Request(base + path, data=data, headers=headers, method=method), timeout=5
            ) as response:
                return response.status, json.load(response)

        for _ in range(40):
            try:
                assert request("/health")[0] == 200
                break
            except URLError, ConnectionError:
                time.sleep(0.5)
        else:
            raise RuntimeError("API did not start")
        assert request("/api/v1/health/ready", token=fixture["alice"])[1]["database"] == "ok"
        _, item = request(
            "/api/v1/items",
            token=fixture["alice"],
            method="POST",
            payload={"name": "GCP baseline preservation probe", "status": "todo"},
        )
        print("Signed-in database readiness and task creation: passed")
        print(docker("exec", api_name, "python", "gcp_migrate.py"))
        _, listing = request("/api/v1/items", token=fixture["alice"])
        assert any(row["id"] == item["id"] for row in listing["items"])
        assert request("/api/v1/items", token=fixture["bob"])[1]["total"] == 0
        for path, method, expected in [
            ("/api/v1/items", "GET", 401),
            ("/local/sign-in", "POST", 404),
        ]:
            try:
                request(path, method=method)
            except HTTPError as error:
                assert error.code == expected
            else:
                raise AssertionError("Expected authentication rejection: " + path)
        assert docker("inspect", "--format", "{{.Config.User}}", api_name) == "10001:10001"
        print(
            "Repeated initialization preserves tasks; "
            "user isolation, auth guards, custom PORT and non-root: passed"
        )
        print("Synthetic task remains in retained PostgreSQL data; no rows were deleted.")
    finally:
        for name in reversed(containers):
            subprocess.run(["docker", "stop", name], capture_output=True)
        print("Stopped and retained smoke containers: " + ", ".join(containers))
        print("Retained PostgreSQL socket volume: " + socket)


if __name__ == "__main__":
    main()
