import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
import sys

from models import Base

# Добавьте путь к вашему проекту
import sys
from os.path import abspath, dirname

sys.path.append(dirname(dirname(abspath(__file__))))

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata


def do_run_migrations(connection):
  context.configure(
    connection=connection,
    target_metadata=target_metadata,
    compare_type=True,
  )
  with context.begin_transaction():
    context.run_migrations()


async def run_async_migrations():
  connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))

  async with connectable.begin() as connection:
    await connection.run_sync(do_run_migrations)

  await connectable.dispose()


def run_migrations_online():
  asyncio.run(run_async_migrations())


if context.is_offline_mode():
  raise Exception("Async migrations not supported in offline mode")
else:
  run_migrations_online()