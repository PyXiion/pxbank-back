# dao/account.py

import random
from typing import Optional, Literal

from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

import models
from database import ensure_loaded
from models import Account, Organization
from pxws.error_with_data import ProtocolError
from .dao import BaseDAO
from .org import OrganizationDAO


async def generate_unique_account_number(session: AsyncSession) -> str:
  for _ in range(10):
    account_number = str(random.randint(100000, 999999))
    stmt = select(exists().where(Account.account_number == account_number))
    exists_result = (await session.execute(stmt)).scalar()
    if not exists_result:
      return account_number

  raise ProtocolError("Не удалось создать счёт. Ошибка подбора номера.")


class AccountDAO(BaseDAO[Account]):
  model = Account

  @classmethod
  async def create(
      cls,
      session: AsyncSession,
      owner: Literal['user', 'org'],
      target_id: int,
      name: str,
      currency_id: int
  ):
    number = await generate_unique_account_number(session)

    acc = Account(
      **{('user_id' if owner == 'user' else 'organization_id'): target_id},
      name=name,
      currency_id=currency_id,
      account_number=number,
    )

    session.add(acc)
    await session.flush()
    return acc

  @classmethod
  async def get_account(
      cls,
      session: AsyncSession,
      account_id: int | str,
      *,
      for_update: bool = True,
      get_user: bool = False,
      get_org: bool = False
  ) -> Optional[Account]:

    id_check = cls.model.id == account_id if isinstance(account_id, int) \
      else cls.model.account_number == account_id

    stmt = (
      select(cls.model)
      .where(id_check, cls.model.is_deleted == False)
    )

    if get_user:
      stmt = stmt.options(joinedload(cls.model.user, innerjoin=False))
    if get_org:
      stmt = stmt.options(joinedload(cls.model.organization, innerjoin=False))
    if for_update:
      stmt = stmt.with_for_update()

    result = await session.execute(stmt)
    return result.scalar_one_or_none()

  @classmethod
  async def can_user_access(cls, session: AsyncSession, user: models.User, account: Account):
    if user.id == account.user_id:
      return True

    await ensure_loaded(session, account, 'organization')
    if not account.organization:
      return False

    org: Organization = account.organization
    if org.owner_id == user.id:
      return True

    role = await OrganizationDAO.get_role_or_none(session, org.id, user.id)
    return bool(role)
