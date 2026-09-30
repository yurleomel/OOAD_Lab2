from collections.abc import AsyncIterator

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import dev_auth
from app.config import Settings, get_settings
from app.db import get_session
from app.main import create_app
from tests.tokens import make_token


def _local_settings(**overrides) -> Settings:
    """What `docker compose up` on a fresh checkout runs with: development, no pool."""
    values = {"app_env": "development", "cognito_user_pool_id": "", "cognito_client_id": ""}
    return Settings(**(values | overrides))


@pytest.fixture(autouse=True)
def _fresh_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(dev_auth, "KEY_PATH", tmp_path / "signing-key.pem")
    dev_auth.signing_key.cache_clear()
    yield
    dev_auth.signing_key.cache_clear()


async def _client_for(settings: Settings, session: AsyncSession) -> AsyncClient:
    app = create_app(settings)

    async def _session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_settings] = lambda: settings
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _sign_in(client: AsyncClient, **body) -> str:
    response = await client.post("/local/sign-in", json=body)
    assert response.status_code == 200
    return response.json()["id_token"]


async def test_sign_in_then_use_the_api(session: AsyncSession) -> None:
    async with await _client_for(_local_settings(), session) as client:
        token = await _sign_in(client, email="Alice@Example.com", name="Alice")

        me = await client.get("/api/v1/me", headers=_bearer(token))
        assert me.status_code == 200
        assert (me.json()["email"], me.json()["name"]) == ("alice@example.com", "Alice")

        created = await client.post("/api/v1/items", json={"name": "Local"}, headers=_bearer(token))
        assert created.status_code == 201


async def test_the_same_email_is_the_same_person(session: AsyncSession) -> None:
    async with await _client_for(_local_settings(), session) as client:
        first = await _sign_in(client, email="alice@example.com")
        second = await _sign_in(client, email="ALICE@example.com")
        ids = [
            (await client.get("/api/v1/me", headers=_bearer(token))).json()["id"]
            for token in (first, second)
        ]
    assert ids[0] == ids[1]


async def test_name_defaults_to_the_email(session: AsyncSession) -> None:
    async with await _client_for(_local_settings(), session) as client:
        token = await _sign_in(client, email="bob@example.com")
        me = (await client.get("/api/v1/me", headers=_bearer(token))).json()
    assert me["name"] == "bob"


async def test_rejects_something_that_is_not_an_email(session: AsyncSession) -> None:
    async with await _client_for(_local_settings(), session) as client:
        response = await client.post("/local/sign-in", json={"email": "not-an-email"})
    assert response.status_code == 422


async def test_a_token_signed_by_another_key_is_refused(session: AsyncSession) -> None:
    forged = make_token(
        key=rsa.generate_private_key(public_exponent=65537, key_size=2048),
        kid="local",
        iss=dev_auth.ISSUER,
        aud=dev_auth.AUDIENCE,
    )
    async with await _client_for(_local_settings(), session) as client:
        response = await client.get("/api/v1/me", headers=_bearer(forged))
    assert response.status_code == 401


async def test_off_outside_development(anon_client: AsyncClient) -> None:
    # The suite runs as APP_ENV=test with a pool configured.
    assert (await anon_client.post("/local/sign-in", json={"email": "a@b.co"})).status_code == 404
    local = dev_auth.mint_token("alice@example.com", "Alice")
    assert (await anon_client.get("/api/v1/me", headers=_bearer(local))).status_code == 401


async def test_off_once_a_pool_is_configured(session: AsyncSession) -> None:
    settings = _local_settings(cognito_user_pool_id="us-east-1_Real", cognito_client_id="c")
    assert not settings.local_sign_in
    async with await _client_for(settings, session) as client:
        response = await client.post("/local/sign-in", json={"email": "a@b.co"})
    assert response.status_code == 404


def test_off_on_lambda(monkeypatch) -> None:
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "peach-backend")
    assert not _local_settings().local_sign_in
