import functools

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

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