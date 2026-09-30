"""Real, signed, Cognito-shaped ID tokens for the test suite.

Importing this module generates an RSA key and points the app at its public
half through COGNITO_JWKS - the same path the Lambda deploy uses - so it must
be imported before app.config is first read. Nothing in app/auth.py is mocked:
every test request goes through the real signature and claim checks.
"""

import json
import os
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

REGION = "us-east-1"
POOL_ID = "us-east-1_TestPool"
CLIENT_ID = "test-app-client"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}"
KEY_ID = "test-key"

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
_jwk.update(kid=KEY_ID, alg="RS256", use="sig")

os.environ.update(
    COGNITO_REGION=REGION,
    COGNITO_USER_POOL_ID=POOL_ID,
    COGNITO_CLIENT_ID=CLIENT_ID,
    COGNITO_JWKS=json.dumps({"keys": [_jwk]}),
)


def make_token(
    sub: str = "alice-sub",
    email: str = "alice@example.com",
    *,
    key: Any = KEY,
    kid: str = KEY_ID,
    **claims: Any,
) -> str:
    """An ID token as the test pool would issue it. A claim passed as None is left out."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "token_use": "id",
        "auth_time": now,
        "iat": now,
        "exp": now + 3600,
        **claims,
    }
    payload = {claim: value for claim, value in payload.items() if value is not None}
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


def auth(**kwargs: Any) -> dict[str, str]:
    """Headers for a request signed in as alice@example.com, unless told otherwise."""
    return {"Authorization": f"Bearer {make_token(**kwargs)}"}
