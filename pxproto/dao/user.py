from typing import Union, Optional, Sequence

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Account
from .dao import BaseDAO

class UserDAO(BaseDAO[User]):
  model = User

  @classmethod
  async def create(cls, session: AsyncSession, username: str, password: str):
    from api.auth import get_hashed_password
    hashed_password = get_hashed_password(password)

    user = User(
      username=username,
      password=hashed_password
    )
    session.add(user)
    await session.flush()
    return user

  @classmethod
  async def set_password(cls, session: AsyncSession, id: str|int, new_password: str):
    from api.auth import get_hashed_password
    hashed_password = get_hashed_password(new_password)

    stmt = update(cls.model)
    if isinstance(id, str):
      stmt = stmt.where(cls.model.username == id)
    else:
      stmt = stmt.where(cls.model.id == id)
    stmt = stmt.values(password=hashed_password)

    await session.execute(stmt)

  @classmethod
  async def get_name_by_id(cls, session: AsyncSession, user_id: int) -> Optional[str]:
    """Получает имя пользователя по его ID"""
    result = await session.execute(
      select(cls.model.username).where(cls.model.id == user_id))
    username = result.scalar_one_or_none()
    return username

  @classmethod
  async def get_id_by_name(cls, session: AsyncSession, name: str) -> Optional[int]:
    """Получает имя пользователя по его ID"""
    result = await session.execute(
      select(cls.model.id).where(cls.model.username == name))
    name = result.scalar_one_or_none()
    return name

  @classmethod
  async def is_admin(cls, session: AsyncSession, user: Union[str, int]) -> bool:
    """Проверяет, является ли пользователь администратором"""
    if isinstance(user, str):
      stmt = select(cls.model.is_admin).where(cls.model.username == user)
    else:
      stmt = select(cls.model.is_admin).where(cls.model.id == user)

    result = await session.execute(stmt)
    is_admin_flag = result.scalar_one_or_none()
    return is_admin_flag is True

  @classmethod
  async def get_user(cls, session: AsyncSession, user_identifier: Union[str, int]) -> Optional[User]:
    """Получает объект пользователя по имени или ID"""
    if isinstance(user_identifier, str):
      result = await session.execute(
        select(cls.model).where(cls.model.username == user_identifier))
    else:
      result = await session.execute(
        select(cls.model).where(cls.model.id == user_identifier))
    return result.scalar_one_or_none()

  @classmethod
  async def search_users(
      cls,
      session: AsyncSession,
      name_part: Optional[str] = None,
      limit: int = 10,
      offset: int = 0
  ) -> Sequence[User]:
    """Поиск пользователей с фильтрацией"""
    stmt = select(cls.model)

    conditions = []
    if name_part:
      conditions.append(cls.model.username.ilike(f"%{name_part}%"))

    if conditions:
      stmt = stmt.where(and_(*conditions))

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all()

  @classmethod
  async def get_user_accounts(
      cls,
      session: AsyncSession,
      username: str,
      public_only: bool,
      limit: int = 10,
      offset: int = 0
  ) -> Sequence[Account]:
    stmt = select(Account).join(cls.model).where(cls.model.username == username)

    if public_only:
      stmt = stmt.where(Account.is_public == True)

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all()