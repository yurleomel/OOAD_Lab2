from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_or_create(session: AsyncSession, *, sub: str, email: str, name: str) -> User:
    """The user behind a verified token: created on first sight, kept in step after that."""
    user = await session.scalar(select(User).where(User.cognito_sub == sub))

    if user is None:
        # A fresh sign-in fires several requests at once, and each of them lands
        # here. ON CONFLICT lets the ones that lose the race fall through to the
        # row the winner inserted instead of failing on the unique constraint.
        await session.execute(
            insert(User)
            .values(cognito_sub=sub, email=email, name=name)
            .on_conflict_do_nothing(index_elements=[User.cognito_sub])
        )
        return await session.scalar(select(User).where(User.cognito_sub == sub))

    if (user.email, user.name) != (email, name):
        user.email = email
        user.name = name
        await session.flush()
        await session.refresh(user)
    return user
