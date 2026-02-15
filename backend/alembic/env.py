import sys
from os.path import abspath, dirname
sys.path.insert(0, dirname(dirname(abspath(__file__))))

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# 1. Import your app settings and metadata
from app.core.config import settings
from app.core.database import Base
from app.domain import models

# 2. Get the Alembic Config object
config = context.config

# 3. OVERRIDE the sqlalchemy.url with the value from our .env/settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
    connection=connection,
    target_metadata=target_metadata,
    # This ensures Alembic only looks at the schema where your tables actually are
    include_schemas=False, 
    # If your models have 'schema="ta"', this will force them into 'public' for now
    version_table_schema=None 
)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # This creates the engine from the URL in alembic.ini or env
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Ensure we are not conflicting with previous schema experiments
            include_schemas=False,
            version_table_schema=None
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()