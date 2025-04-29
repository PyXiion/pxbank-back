from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

import models
from database import ensure_loaded
from models import Account, Organization
from .dao import BaseDAO
from .org import OrganizationDAO


class AccountDAO(BaseDAO[Account]):
  model = Account
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
      .where(
        id_check,
        cls.model.is_deleted == False
      )
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