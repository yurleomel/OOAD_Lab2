import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item
from app.schemas import ItemCreate, ItemUpdate

# Every query is scoped to one owner: nobody can list, read or change an item
# that is not theirs, and someone else's item looks exactly like a missing one.


async def list_items(
    session: AsyncSession, owner_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[Item], int]:
    total = (
        await session.scalar(
            select(func.count()).select_from(Item).where(Item.owner_id == owner_id)
        )
        or 0
    )
    result = await session.execute(
        select(Item)
        .where(Item.owner_id == owner_id)
        .order_by(Item.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars()), total


async def get_item(session: AsyncSession, owner_id: uuid.UUID, item_id: uuid.UUID) -> Item | None:
    return await session.scalar(select(Item).where(Item.id == item_id, Item.owner_id == owner_id))


async def create_item(session: AsyncSession, owner_id: uuid.UUID, payload: ItemCreate) -> Item:
    # mode="json": the agenda goes into JSONB, where a datetime must be a string.
    item = Item(owner_id=owner_id, **payload.model_dump(mode="json"))
    if item.status == "done":
        item.completed_at = func.now()
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return item


async def update_item(session: AsyncSession, item: Item, payload: ItemUpdate) -> Item:
    was_done = item.status == "done"
    for field, value in payload.model_dump(mode="json", exclude_unset=True).items():
        setattr(item, field, value)
    # Only a transition moves completed_at: renaming a finished item must not
    # make it count as finished again this week.
    if item.status == "done" and not was_done:
        item.completed_at = func.now()
    elif item.status != "done":
        item.completed_at = None
    await session.flush()
    await session.refresh(item)
    return item


async def delete_item(session: AsyncSession, item: Item) -> None:
    await session.delete(item)
    await session.flush()
