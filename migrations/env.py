from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import DATABASE_URL

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No ORM models - schema is raw SQL (see db/schema.sql and versions/0001).
# target_metadata stays None; autogenerate is not used in this project.
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # DATABASE_URL is a plain "postgresql://" DSN (shared with app/db.py, which
    # hands it to psycopg3 directly); SQLAlchemy needs the driver in the scheme.
    sqlalchemy_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    connectable = create_engine(sqlalchemy_url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
