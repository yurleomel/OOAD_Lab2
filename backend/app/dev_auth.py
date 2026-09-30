"""Local sign-in for `docker compose up` on a fresh checkout: no Cognito, no AWS.

Active only when APP_ENV is development, no user pool is configured, and the
code is not running on Lambda (see Settings.local_sign_in). Its tokens are
RS256 and shaped like Cognito ID tokens, and app/auth.py checks them with the
same code - signature, issuer, audience, expiry, token_use - they are just
signed by a key this container keeps instead of by a user pool.
"""

import hashlib
import os
import re
import tempfile
import time
from functools import lru_cache
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

ISSUER = "http://localhost/peach-local-sign-in"
AUDIENCE = "peach-local"
TOKEN_LIFETIME_SECONDS = 12 * 3600

# In the temp dir, so `uvicorn --reload` restarts keep it and nobody signs out on
# every code change; a new container starts with a new key.
KEY_PATH = Path(tempfile.gettempdir()) / "peach-local-signing-key.pem"


@lru_cache
def signing_key() -> rsa.RSAPrivateKey:
    if KEY_PATH.exists():
        key = serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=None)
        if isinstance(key, rsa.RSAPrivateKey):
            return key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    fd = os.open(KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(pem)
    return key


def mint_token(email: str, name: str) -> str:
    now = int(time.time())
    # The same email is the same person across sign-ins, like a Cognito sub.
    sub = "local-" + hashlib.sha256(email.encode()).hexdigest()[:32]
    claims = {
        "sub": sub,
        "email": email,
        "name": name,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "token_use": "id",
        "iat": now,
        "exp": now + TOKEN_LIFETIME_SECONDS,
    }
    return jwt.encode(claims, signing_key(), algorithm="RS256", headers={"kid": "local"})


class LocalSignIn(BaseModel):
    email: str = Field(max_length=320)
    name: str = Field(default="", max_length=120)

    @field_validator("email")
    @classmethod
    def _looks_like_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("not an email address")
        return value


class LocalToken(BaseModel):
    id_token: str


router = APIRouter(prefix="/local", tags=["local sign-in"])


@router.post("/sign-in", response_model=LocalToken, summary="Local development sign-in")
async def local_sign_in(payload: LocalSignIn) -> LocalToken:
    """Any email, no password: a signed ID token for it. Registered only in local development."""
    name = payload.name.strip() or payload.email.split("@", 1)[0]
    return LocalToken(id_token=mint_token(payload.email, name))
