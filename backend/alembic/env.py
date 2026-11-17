import importlib
import pkgutil

from alembic import context
from logging.config import fileConfig

from app.database import Base, DATABASE_URL, engine
from app import models as model_package

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all model modules so SQLAlchemy metadata contains every table.
if hasattr(model_package, "__path__"):
    for module in pkgutil.walk_packages(
        model_package.__path__,
        prefix=model_package.__name__ + ".",
    ):
        importlib.import_module(module.name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=DATABASE_URL.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()