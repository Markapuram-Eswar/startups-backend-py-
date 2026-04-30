"""Alembic env — uses same DB URL as the FastAPI app (existing Prisma/RDS schema)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.database import Base
from app.db_url import get_connect_args, get_database_url

# Ensure model tables are registered on Base.metadata
from app.models import *  # noqa: F401, F403

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_database_url()
    connect_args = get_connect_args()
    connectable = create_engine(url, pool_pre_ping=True, connect_args=connect_args)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
