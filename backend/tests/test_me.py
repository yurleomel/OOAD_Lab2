from httpx import AsyncClient

from tests.tokens import auth


async def test_first_request_creates_the_user(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "email", "name", "created_at"}
    assert body["email"] == "alice@example.com"
    # No name claim: the part of the email before the @ stands in.
    assert body["name"] == "alice"


async def test_later_requests_reuse_the_user(client: AsyncClient) -> None:
    first = (await client.get("/api/v1/me")).json()
    second = (await client.get("/api/v1/me")).json()
    assert second["id"] == first["id"]


async def test_name_claim_is_used(anon_client: AsyncClient) -> None:
    body = (await anon_client.get("/api/v1/me", headers=auth(name="Alice Liddell"))).json()
    assert body["name"] == "Alice Liddell"


async def test_email_and_name_follow_the_token(anon_client: AsyncClient) -> None:
    before = (await anon_client.get("/api/v1/me", headers=auth())).json()
    renamed = auth(email="alice@new.example.com", name="Alice L.")
    after = (await anon_client.get("/api/v1/me", headers=renamed)).json()
    assert after["id"] == before["id"]
    assert (after["email"], after["name"]) == ("alice@new.example.com", "Alice L.")


async def test_people_are_told_apart_by_sub_not_email(anon_client: AsyncClient) -> None:
    alice = (await anon_client.get("/api/v1/me", headers=auth())).json()
    namesake = (await anon_client.get("/api/v1/me", headers=auth(sub="another-sub"))).json()
    assert namesake["id"] != alice["id"]
