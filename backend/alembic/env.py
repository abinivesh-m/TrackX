# backend/alembic/env.py

import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import all models
from app.core.database import Base
import app.models.camera
import app.models.observation
import app.models.vehicle
import app.models.alert
import app.models.audit_log
import app.models.user

# Alembic Config
config = context.config

# Set database URL from environment
config.set_main_option(
    "sqlalchemy.url",
    os.getenv(
        "DATABASE_URL",
        # Dev default is SQLite so a clean checkout can run migrations locally
        # without a PostgreSQL server. Production MUST set DATABASE_URL via env.
        "sqlite:///backend/trackx.db",
    )
)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
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


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
