import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item
from tests.tokens import make_token


async def test_list_is_empty_initially(client: AsyncClient) -> None:
    response = await client.get("/api/v1/items")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_create_returns_201_and_the_item(client: AsyncClient) -> None:
    response = await client.post("/api/v1/items", json={"name": "First", "description": "hello"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "First"
    assert body["description"] == "hello"
    assert body["status"] == "todo"
    assert uuid.UUID(body["id"])
    assert body["created_at"] and body["updated_at"]


async def test_create_rejects_empty_name(client: AsyncClient) -> None:
    response = await client.post("/api/v1/items", json={"name": ""})
    assert response.status_code == 422


async def test_get_roundtrips(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/items", json={"name": "Fetch me"})).json()
    response = await client.get(f"/api/v1/items/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_missing_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/items/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


async def test_patch_applies_partial_update(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/items", json={"name": "Before"})).json()
    response = await client.patch(f"/api/v1/items/{created['id']}", json={"status": "in_progress"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["name"] == "Before"


async def test_rejects_unknown_status(client: AsyncClient) -> None:
    response = await client.post("/api/v1/items", json={"name": "Bad", "status": "blocked"})
    assert response.status_code == 422


async def test_patch_missing_returns_404(client: AsyncClient) -> None:
    response = await client.patch(f"/api/v1/items/{uuid.uuid4()}", json={"name": "x"})
    assert response.status_code == 404


async def test_delete_returns_204_then_404(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/items", json={"name": "Doomed"})).json()
    assert (await client.delete(f"/api/v1/items/{created['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/items/{created['id']}")).status_code == 404


async def test_delete_missing_returns_404(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/items/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_pagination(client: AsyncClient) -> None:
    for index in range(3):
        await client.post("/api/v1/items", json={"name": f"Item {index}"})
    response = await client.get("/api/v1/items", params={"limit": 2, "offset": 0})
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_pagination_rejects_bad_limit(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/items", params={"limit": 0})).status_code == 422
    assert (await client.get("/api/v1/items", params={"limit": 101})).status_code == 422


async def test_items_are_private_to_their_owner(client: AsyncClient) -> None:
    mine = (await client.post("/api/v1/items", json={"name": "Alice's"})).json()
    bob = {"Authorization": f"Bearer {make_token('bob-sub', 'bob@example.com')}"}

    listing = (await client.get("/api/v1/items", headers=bob)).json()
    assert listing == {"items": [], "total": 0}

    # Someone else's item is indistinguishable from a missing one.
    url = f"/api/v1/items/{mine['id']}"
    assert (await client.get(url, headers=bob)).status_code == 404
    assert (await client.patch(url, json={"name": "mine now"}, headers=bob)).status_code == 404
    assert (await client.delete(url, headers=bob)).status_code == 404

    # Untouched for its owner.
    assert (await client.get(url)).json()["name"] == "Alice's"


# --- completed_at, which the weekly report counts by --------------------------


async def _completed_at(session: AsyncSession, item_id: str) -> datetime | None:
    item = await session.get(Item, uuid.UUID(item_id))
    assert item is not None
    await session.refresh(item)
    return item.completed_at


async def test_completed_at_is_set_when_an_item_is_done(
    client: AsyncClient, session: AsyncSession
) -> None:
    created = (await client.post("/api/v1/items", json={"name": "Ship it"})).json()
    assert await _completed_at(session, created["id"]) is None

    await client.patch(f"/api/v1/items/{created['id']}", json={"status": "done"})
    assert await _completed_at(session, created["id"]) is not None


async def test_an_item_created_done_is_completed(
    client: AsyncClient, session: AsyncSession
) -> None:
    created = (
        await client.post("/api/v1/items", json={"name": "Already", "status": "done"})
    ).json()
    assert await _completed_at(session, created["id"]) is not None


async def test_editing_a_done_item_keeps_its_completion_time(
    client: AsyncClient, session: AsyncSession
) -> None:
    created = (await client.post("/api/v1/items", json={"name": "Old", "status": "done"})).json()
    item = await session.get(Item, uuid.UUID(created["id"]))
    assert item is not None
    finished = datetime(2026, 9, 1, tzinfo=UTC)
    item.completed_at = finished
    await session.flush()

    await client.patch(f"/api/v1/items/{created['id']}", json={"name": "Renamed"})
    await client.patch(f"/api/v1/items/{created['id']}", json={"status": "done"})
    assert await _completed_at(session, created["id"]) == finished


async def test_reopening_an_item_clears_its_completion(
    client: AsyncClient, session: AsyncSession
) -> None:
    created = (await client.post("/api/v1/items", json={"name": "Again", "status": "done"})).json()
    await client.patch(f"/api/v1/items/{created['id']}", json={"status": "in_progress"})
    assert await _completed_at(session, created["id"]) is None
