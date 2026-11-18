import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.engine import make_url
from sqlalchemy import text

from alembic import context

from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Use a guarded, explicit URL for disposable PostgreSQL verification. ---
# This branch intentionally never imports application settings, which read
# .env. It accepts only the fixed local test identity below.
test_database_url = os.environ.get("ZETICKETS_TEST_DATABASE_URL")
test_database_identity = None
if test_database_url:
    test_database_identity = {
        "host": "127.0.0.1",
        "port": 55439,
        "database": "zetickets_phase2_test",
        "username": "zetickets_test_owner",
    }
    parsed_test_url = make_url(test_database_url)
    actual_test_identity = {
        "host": parsed_test_url.host,
        "port": parsed_test_url.port,
        "database": parsed_test_url.database,
        "username": parsed_test_url.username,
    }
    if parsed_test_url.drivername != "postgresql+asyncpg" or actual_test_identity != test_database_identity:
        raise RuntimeError("Refusing migration: test URL is not the dedicated Zetickets loopback database")
    test_cluster_id = os.environ.get("ZETICKETS_TEST_CLUSTER_ID")
    if not test_cluster_id:
        raise RuntimeError("Refusing migration: ZETICKETS_TEST_CLUSTER_ID is required for disposable PostgreSQL verification")
    database_url = test_database_url
else:
    from app.core.config import settings

    database_url = settings.SQL_ALCHEMY_DATABASE_URI

escaped_uri = database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", escaped_uri)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    if test_database_identity is not None:
        identity = connection.execute(
            text(
                "SELECT current_database() AS database, host(inet_server_addr()) AS host, "
                "inet_server_port() AS port, current_user AS username, "
                "(pg_control_system()).system_identifier::text AS cluster_id"
            )
        ).mappings().one()
        actual = {
            "host": identity["host"],
            "port": identity["port"],
            "database": identity["database"],
            "username": identity["username"],
        }
        if actual != test_database_identity:
            raise RuntimeError("Refusing migration: connected PostgreSQL identity does not match the disposable test target")
        if identity["cluster_id"] != test_cluster_id:
            raise RuntimeError("Refusing migration: PostgreSQL cluster identifier does not match the disposable test cluster")
        # The identity SELECT triggers SQLAlchemy autobegin. Commit that
        # read-only preflight so Alembic owns and commits the migration
        # transaction below instead of inheriting a caller-owned transaction.
        connection.commit()

    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we create an async Engine and run migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
