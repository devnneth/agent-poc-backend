from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlmodel import SQLModel

from alembic import context
from app.infrastructure.models.google_calendar_event_model import (  # noqa: F401
    GoogleCalendarEventModel,
)
from app.infrastructure.models.event_embedding_model import (  # noqa: F401
    EventEmbeddingBaseModel,
    EventEmbedding1024Model,
    EventEmbedding1536Model,
    EventEmbedding768Model,
)
from app.infrastructure.models.todo_model import TodoModel  # noqa: F401
from app.infrastructure.models.memo_model import MemoModel  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
  fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def include_object(object, name, type_, reflected, compare_to):
  """'auth' 스키마 및 LangGraph 체크포인트 테이블 등 Alembic이 관리하지 않아야 할 객체들을 필터링합니다."""
  if type_ == "table":
    if getattr(object, "schema", None) == "auth":
      return False
    # LangGraph 관련 테이블 보호
    langgraph_tables = {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
    if name in langgraph_tables:
      return False
  return True


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
    include_object=include_object,
    version_table_schema="private",  # alembic_version 테이블 RLS 경고 해제를 위함.
                                   # private 스키마를 만든다.
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
    context.configure(
      connection=connection,
      target_metadata=target_metadata,
      include_object=include_object,
      version_table_schema="private",  # alembic_version 테이블 RLS 경고 해제를 위함.
                                     # private 스키마를 만든다.
    )

    with context.begin_transaction():
      context.run_migrations()


if context.is_offline_mode():
  run_migrations_offline()
else:
  run_migrations_online()
