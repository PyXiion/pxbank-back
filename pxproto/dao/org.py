from typing import Coroutine

from sqlalchemy import or_, select, func, delete, insert, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload, selectinload

from models import Transaction, Account, User, Organization, OrganizationMember, OrganizationRole
from .dao import BaseDAO


class OrganizationDAO(BaseDAO[Organization]):
  model = Organization

  @classmethod
  async def create(cls, session: AsyncSession, user_id: int, name: str):
    org = Organization(
      name=name,
      owner_id=user_id
    )

    session.add(org)
    await session.flush()
    return org

  @classmethod
  async def rename(cls, session: AsyncSession, org_id: int, name: str):
    await session.execute(update(cls.model), [{'id': org_id, 'name': name}])
    await session.commit()

  @classmethod
  async def owned_count(cls, session: AsyncSession, user_id: int):
    stmt = select(func.count()).select_from(cls.model).where(cls.model.owner_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one()

  @classmethod
  async def account_limit(cls, session: AsyncSession, org_id):
    stmt = select(cls.model.account_limit).where(cls.model.id == org_id)
    result = await session.execute(stmt)
    return result.scalar_one()

  @classmethod
  async def member_count(cls, session: AsyncSession, org_id: int) -> Coroutine[int, None, None]:
    stmt = select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == org_id)
    result = await session.execute(stmt)
    return result.scalar_one() + 1 # + owner

  @classmethod
  async def get_one(cls, session: AsyncSession, org_id: int, /, *, members: bool = False) -> Organization:
    stmt = select(cls.model).where(cls.model.id == org_id)

    if members:
      stmt = stmt.options(selectinload(cls.model.members).selectinload(OrganizationMember.user), selectinload(cls.model.owner))

    result = await session.execute(stmt)
    return result.scalar_one_or_none()

  @classmethod
  async def get_org_field(cls, session: AsyncSession, org_id: int, field: str) -> Organization:
    stmt = select(getattr(cls.model, field)).where(cls.model.id == org_id)

    result = await session.execute(stmt)
    return result.scalar_one_or_none()

  @classmethod
  async def get_user_organizations_with_roles(cls, session: AsyncSession, user_id: int):
    # Получаем все организации, где пользователь владелец
    owner_stmt = (
      select(Organization)
      .where(Organization.owner_id == user_id)
    )
    owner_result = await session.execute(owner_stmt)
    owner_orgs = owner_result.scalars().all()

    owner_ids = {org.id for org in owner_orgs}
    owner_list = [
      (await org.to_dict()) | {"access_role": OrganizationRole.OWNER.value}
      for org in owner_orgs
    ]

    # Получаем все организации, где пользователь является участником
    member_stmt = (
      select(OrganizationMember)
      .options(joinedload(OrganizationMember.organization))
      .where(OrganizationMember.user_id == user_id)
    )
    member_result = await session.execute(member_stmt)
    member_orgs = member_result.scalars().all()

    member_list = []
    for member in member_orgs:
      org = member.organization
      if org.id not in owner_ids:
        member_list.append(
          (await org.to_dict()) | {"access_role": member.role.value}
        )

    return owner_list + member_list

  @classmethod
  async def get_role_or_none(cls, session: AsyncSession, org_id: int, user_id: int):
    # Сначала проверим, является ли пользователь владельцем организации
    owner_stmt = select(cls.model.owner_id).where(cls.model.id == org_id)
    owner_result = await session.execute(owner_stmt)
    owner_id = owner_result.scalar_one_or_none()

    if owner_id is not None and owner_id == user_id:
      return OrganizationRole.OWNER

    # Если не владелец — ищем роль из OrganizationMember
    stmt = (
      select(OrganizationMember.role)
      .where(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user_id
      )
    )

    result = await session.execute(stmt)
    return result.scalar_one_or_none()

  @classmethod
  async def get_accounts_for_user(cls, session: AsyncSession, org_id: int, user_id: int):
    stmt = (
      select(
        Account
      )
      .where(
        Account.organization_id == org_id,
        Account.is_deleted == False
      )
    )

    result = await session.execute(stmt)
    return result.scalars().all()

  @classmethod
  async def get_public_accounts(cls, session: AsyncSession, org_id: int):
    stmt = (
      select(
        Account
      )
      .where(
        Account.organization_id == org_id,
        Account.is_public == True,
        Account.is_deleted == False
      )
    )

    result = await session.execute(stmt)
    return result.scalars().all()

  @classmethod
  async def kick(cls, session: AsyncSession, org_id: int, target: int | str):
    """Удаляет участника из организации (по ID или имени пользователя), кроме владельца."""
    if isinstance(target, str):
      subquery = select(User.id).where(User.username == target).limit(1)
      result = await session.execute(subquery)
      target = result.scalar_one_or_none()
      if target is None:
        raise ValueError(f"Пользователь с именем '{target}' не найден.")

    # Защита от удаления владельца
    owner_stmt = select(cls.model.owner_id).where(cls.model.id == org_id)
    owner_result = await session.execute(owner_stmt)
    owner_id = owner_result.scalar_one()

    if owner_id == target:
      raise ValueError("Нельзя удалить владельца организации.")

    stmt = delete(OrganizationMember).where(
      OrganizationMember.organization_id == org_id,
      OrganizationMember.user_id == target
    )
    await session.execute(stmt)

  @classmethod
  async def member_count_and_limit(cls, session: AsyncSession, org_id: int) -> tuple[int, int]:
    """
    Возвращает текущее количество участников и лимит участников для организации.

    :returns: (member_count, member_limit)
    """
    result = await session.execute(
      select(func.count(OrganizationMember.user_id))
      .where(OrganizationMember.organization_id == org_id)
    )
    member_count = result.scalar_one() + 1 # + owner

    result = await session.execute(
      select(cls.model.member_limit)
      .where(cls.model.id == org_id)
    )
    member_limit = result.scalar_one()

    return member_count, member_limit

  @classmethod
  async def add_user(cls, session: AsyncSession, org_id: int, user_id: int,
                     role: OrganizationRole = OrganizationRole.MEMBER):
    """Добавляет пользователя в организацию с указанной ролью (MySQL-safe)."""
    stmt = insert(OrganizationMember).values(
      organization_id=org_id,
      user_id=user_id,
      role=role
    ).on_duplicate_key_update(role=OrganizationMember.role)  # ничего не меняем, просто игнорируем

    await session.execute(stmt)

  @classmethod
  async def set_role(cls, session: AsyncSession, org_id: int, user_id: int, role: OrganizationRole):
    """Устанавливает пользователю новую роль в организации."""
    stmt = update(OrganizationMember).where(
      OrganizationMember.organization_id == org_id,
      OrganizationMember.user_id == user_id
    ).values(role=role)

    result = await session.execute(stmt)
    if result.rowcount == 0:
      raise ValueError("Пользователь не является участником организации.")