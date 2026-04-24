"""Alembic Environment Configuration for AxiomFolio"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context
import os
import sys

# Add the proper paths for the backend directory
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)

sys.path.insert(0, project_root)
sys.path.insert(0, backend_dir)

# Import the database configuration and models
from app.database import DATABASE_URL
from app.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override the database URL from config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Fail fast when another session holds DDL-heavy locks (e.g. Celery, long
        # queries). Without this, API startup can hang until Render kills the
        # instance; the log in main.py referred to these but they were not applied.
        connection.execute(text("SET lock_timeout = '10s'"))
        connection.execute(text("SET statement_timeout = '30s'"))
        # SQLAlchemy 2.x autobegins on first execute(); commit that implicit
        # transaction here so Alembic owns the next BEGIN. Without this commit,
        # `context.begin_transaction()` sees an "external" transaction, returns
        # `nullcontext()` without setting `self._transaction`, and any migration
        # using `op.get_context().autocommit_block()` (e.g. CREATE INDEX
        # CONCURRENTLY in 0022) trips an internal AssertionError. The SET
        # statements are session-scoped and survive the COMMIT.
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
