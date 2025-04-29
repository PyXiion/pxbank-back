import functools

from sqlalchemy import NullPool, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import RelationshipProperty, selectinload
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm.attributes import NEVER_SET, NO_VALUE

SQLALCHEMY_DATABASE_URL = "mysql+asyncmy://pxproto:pxproto@localhost:3306/pxdb"

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool)

SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


def get_db():
  return SessionLocal()


def connection(method):
  @functools.wraps(method)
  async def wrapper(*args, **kwargs):
    async with SessionLocal() as session:
      try:
        return await method(*args, session=session, **kwargs)
      except Exception as e:
        await session.rollback()
        raise
      finally:
        await session.close()

  return wrapper


async def ensure_loaded(
    session: AsyncSession,
    instance: object,
    relationship_name: str,
    load_strategy: str = "select"
) -> None:
  """
  Убеждается, что relationship атрибут загружен.
  Если нет, то загружает его указанной стратегией.

  Параметры:
      session: AsyncSession
      instance: Объект модели SQLAlchemy
      relationship_name: Имя relationship-атрибута
      load_strategy: "select" (по умолчанию) или "joined"

  "select" через resfresh, а "joined" через отдельный запрос

  Пример:
      await ensure_loaded(session, user, "organization")
  """
  if not hasattr(instance.__class__, relationship_name):
    raise AttributeError(f"'{instance.__class__.__name__}' has no relationship '{relationship_name}'")

  prop = getattr(instance.__class__, relationship_name).property
  if not isinstance(prop, RelationshipProperty):
    raise AttributeError(f"'{relationship_name}' is not a relationship attribute")

  # Проверяем, загружен ли атрибут
  if relationship_name in instance.__dict__:
    return  # Уже загружен

  current_value = getattr(instance, relationship_name)
  if current_value not in [None, NEVER_SET, NO_VALUE]:
    return  # Уже загружен (имеет значение)

  # Загружаем relationship
  if load_strategy == "select":
    await session.refresh(instance, [relationship_name])
  elif load_strategy == "joined":
    stmt = (
      select(instance.__class__)
      .where(instance.__class__.id == instance.id)
      .options(selectinload(getattr(instance.__class__, relationship_name)))
    )
    result = await session.execute(stmt)
    reloaded = result.scalars().first()
    if reloaded:
      setattr(instance, relationship_name, getattr(reloaded, relationship_name))
  else:
    raise ValueError(f"Unknown load strategy: {load_strategy}")
