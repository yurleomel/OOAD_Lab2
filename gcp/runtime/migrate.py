"""Initialize an empty GCP database without replaying historical removals.

The additive baseline is at revision 0005. Later schema changes require an
explicitly reviewed upgrade of this job; this script refuses a newer head.
It never runs create_all(), drops structures, clears rows or executes downgrade.
"""

import asyncio
import subprocess
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

BASELINE_REVISION = "0005"


async def initialize() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    if script.get_current_head() != BASELINE_REVISION:
        raise RuntimeError("Schema head changed: review the GCP migration job before running it")

    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT pg_advisory_xact_lock(900005)"))
            tables = set(
                (
                    await connection.scalars(
                        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                    )
                ).all()
            )
            if tables:
                if not {"users", "items", "alembic_version"}.issubset(tables):
                    raise RuntimeError("Database is not empty and is not the expected GCP baseline")
                versions = (
                    await connection.scalars(text("SELECT version_num FROM alembic_version"))
                ).all()
                if versions != [BASELINE_REVISION]:
                    raise RuntimeError(
                        "Existing database revision differs: automatic changes refused"
                    )
                print("Database already at GCP baseline 0005; all rows preserved.")
                return

            sql = "\n".join(
                line
                for line in Path(__file__).with_name("baseline.sql").read_text().splitlines()
                if not line.lstrip().startswith("--")
            )
            for statement in sql.split(";"):
                if statement.strip():
                    await connection.execute(text(statement))
            print(
                "Created empty GCP schema at revision 0005 without replaying historical upgrades."
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(initialize())
    subprocess.run(["alembic", "check"], check=True)
