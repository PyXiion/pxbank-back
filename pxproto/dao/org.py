from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload

from models import Transaction, Account, User, Organization, OrganizationMember, OrganizationRole
from .dao import BaseDAO


class OrganizationDAO(BaseDAO[Organization]):
  model = Organization

  @classmethod
  async def get_user_organizations_with_roles(cls, session: AsyncSession, user_id: int):
    owner_stmt = (
      select(Organization)
      .options(joinedload(Organization.members))
      .where(Organization.owner_id == user_id)
    )
    owner_result = await session.execute(owner_stmt)
    owner_orgs = owner_result.scalars().all()

    owner_list = [
      org.to_dict() |  {
        "role": OrganizationRole.OWNER.value
      }
      for org in owner_orgs
    ]

    # Как член (не владелец)
    member_stmt = (
      select(OrganizationMember)
      .options(joinedload(OrganizationMember.organization))
      .where(OrganizationMember.user_id == user_id)
    )
    member_result = await session.execute(member_stmt)
    member_orgs = member_result.scalars().all()

    member_list = [
      member.organization.to_dict() |  {
        "role": member.role.value
      }
      for member in member_orgs
      if member.organization.owner_id != user_id  # чтобы не дублировать владельцев
    ]

    return owner_list + member_list

  @classmethod
  async def get_role_or_none(cls, session: AsyncSession, org_id: int, user_id: int):
    stmt = (
      select(
        OrganizationMember.role
      )
      .where(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user_id
      )
    )

    result = await session.execute(stmt)
    return result.scalar_one_or_none()