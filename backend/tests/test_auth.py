import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.main import create_app
from tests.tokens import make_token

PROTECTED = "/api/v1/items"
_FOREIGN_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


REJECTED = {
    "garbage": _bearer("not-a-jwt"),
    "wrong scheme": {"Authorization": f"Basic {make_token()}"},
    "unsigned": _bearer(jwt.encode({"sub": "alice-sub"}, None, algorithm="none")),
    "signed by another key": _bearer(make_token(key=_FOREIGN_KEY)),
    "unknown key id": _bearer(make_token(kid="rotated-away")),
    "expired": _bearer(make_token(exp=int(time.time()) - 60)),
    "another app client": _bearer(make_token(aud="someone-elses-client")),
    "another user pool": _bearer(
        make_token(iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Other")
    ),
    "access token": _bearer(make_token(token_use="access")),
    "no token_use": _bearer(make_token(token_use=None)),
    "no email": _bearer(make_token(email=None)),
}


@pytest.mark.parametrize("headers", REJECTED.values(), ids=REJECTED.keys())
async def test_bad_credentials_are_401(anon_client: AsyncClient, headers: dict) -> None:
    response = await anon_client.get(PROTECTED, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("path", ["/api/v1/items", "/api/v1/me", "/api/v1/health/ready"])
async def test_every_api_route_needs_a_token(anon_client: AsyncClient, path: str) -> None:
    response = await anon_client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_liveness_needs_no_token(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/health")).status_code == 200


async def test_no_user_pool_is_503_never_open(session: AsyncSession) -> None:
    app = create_app()

    async def _session():
        yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_settings] = lambda: Settings(
        cognito_user_pool_id="", cognito_client_id=""
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(PROTECTED, headers=_bearer(make_token()))
    assert response.status_code == 503
