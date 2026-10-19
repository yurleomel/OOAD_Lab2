"""An agenda is part of a task: saved through the items endpoints, with their validation."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item

AGENDA = {
    "starts_at": "2026-10-19T10:00:00+03:00",
    "duration_minutes": 45,
    "items": [
        {"topic": "нові тарифи Pro", "owner": "Олена", "minutes": 15},
        {"topic": "фідбек від клієнтів", "owner": "Taras", "minutes": None},
    ],
    "action_items": [{"task": "порівняння з конкурентами", "owner": "Taras", "due": "2026-10-23"}],
}

SUGGESTION = {
    "agenda": {
        "title": "синк по прайсингу",
        "starts_at": "2026-10-19T10:00:00+03:00",
        "duration_minutes": 45,
        "items": [{"topic": "нові тарифи Pro", "owner": "Олена", "minutes": 15}],
        "action_items": [],
        "language": "uk",
    },
    "model": "anthropic.claude-opus-5-5",
    "prompt_version": "agenda-v1",
}


async def test_a_task_has_no_agenda_by_default(client: AsyncClient) -> None:
    body = (await client.post("/api/v1/items", json={"name": "Plain"})).json()
    assert body["agenda"] is None


async def test_create_with_agenda_and_suggestion(
    client: AsyncClient, session: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/items",
        json={"name": "Pricing sync", "agenda": AGENDA, "ai_suggestion": SUGGESTION},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["agenda"]["items"][0] == AGENDA["items"][0]
    assert body["agenda"]["action_items"][0]["due"] == "2026-10-23"
    # Read back, the suggestion stays server-side: it is for offline comparison.
    assert "ai_suggestion" not in body

    item = await session.get(Item, body["id"])
    assert item is not None
    assert item.ai_suggestion == SUGGESTION
    # JSONB holds strings, not datetimes.
    assert item.agenda is not None and item.agenda["starts_at"].startswith("2026-10-19T")


async def test_patch_adds_keeps_and_removes_the_agenda(client: AsyncClient) -> None:
    item = (await client.post("/api/v1/items", json={"name": "Meeting"})).json()
    url = f"/api/v1/items/{item['id']}"

    added = (await client.patch(url, json={"agenda": AGENDA})).json()
    assert len(added["agenda"]["items"]) == 2

    renamed = (await client.patch(url, json={"name": "Renamed"})).json()
    assert renamed["agenda"] == added["agenda"]

    removed = (await client.patch(url, json={"agenda": None})).json()
    assert removed["agenda"] is None


async def test_agenda_is_validated(client: AsyncClient) -> None:
    for bad in (
        {"items": [{"topic": ""}]},
        {"items": [{"topic": "x", "minutes": 0}]},
        {"items": [], "duration_minutes": 601},
        {"items": [], "action_items": [{"task": "x", "due": "next friday"}]},
        {"items": [{"topic": "x"}] * 51},
    ):
        response = await client.post("/api/v1/items", json={"name": "Bad", "agenda": bad})
        assert response.status_code == 422, bad


async def test_suggestion_is_validated(client: AsyncClient) -> None:
    junk = {**SUGGESTION, "agenda": {"anything": "goes"}}
    response = await client.post(
        "/api/v1/items", json={"name": "Bad", "agenda": AGENDA, "ai_suggestion": junk}
    )
    assert response.status_code == 422
