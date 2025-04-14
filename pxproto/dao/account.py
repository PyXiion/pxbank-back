from typing import Union, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models import Account
from .dao import BaseDAO

class AccountDAO(BaseDAO[Account]):
  model = Account

  @classmethod
  async def get_account(cls, session: AsyncSession, account_id: int | str) -> Optional[Account]:
    if isinstance(account_id, int):
      result = await session.execute(
        select(cls.model).where(cls.model.id == account_id, cls.model.is_deleted == False))
    else:
      result = await session.execute(
        select(cls.model).where(cls.model.account_number == account_id, cls.model.is_deleted == False))
    return result.scalar_one_or_none()

  @classmethod
  async def get_account_and_user(cls, session: AsyncSession, account_id: int | str) -> Optional[Account]:
    if isinstance(account_id, int):
      stmt = select(cls.model).options(joinedload(cls.model.user)).where(
        cls.model.id == account_id,
        cls.model.is_deleted == False
      )
    else:
      stmt = select(cls.model).options(joinedload(cls.model.user)).where(
        cls.model.account_number == account_id,
        cls.model.is_deleted == False
      )

    result = await session.execute(stmt)
    return result.scalar_one_or_none()