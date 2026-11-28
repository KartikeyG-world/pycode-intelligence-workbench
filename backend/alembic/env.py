import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Make the backend package importable when Alembic is run from backend/.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.database import Base
from app.models.models import User, Project, CodeSubmission, AnalysisResult  # noqa: F401

config = context.config

# Configure Alembic's logger from backend/alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing the ORM models above registers their tables on Base.metadata.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a DBAPI connection."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using the configured application database URL."""
    # Pass the URL directly rather than through ConfigParser interpolation.
    # This supports percent-encoded characters in database credentials.
    connectable = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
