import asyncio
from typing import Sequence

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

import database
import proto_models
from dao import UserDAO
from dao.org import OrganizationDAO
from dao.push_service import PushService
from models import Organization, OrganizationRole
from pxws.connection_ctx import ConnectionContext
from pxws.error_with_data import ProtocolError
from pxws.route import Route

route = Route()


async def with_member_count(s: AsyncSession, orgs: Sequence[Organization]):
  return [
    org | {
      'member_count': await OrganizationDAO.member_count(s, org['id'])
    }
    for org in orgs
  ]


@route.on('org/list', require_auth=True, ignore_params=['session'])
@database.connection
async def org_list(ctx: ConnectionContext, session: AsyncSession):
  return await with_member_count(session, await OrganizationDAO.get_user_organizations_with_roles(session,
                                                                                                  ctx.get_metadata(
                                                                                                    'user_id')))


@route.on('org/fetch', require_auth=True, ignore_params=['session'])
@database.connection
async def org_fetch(ctx: ConnectionContext, session: AsyncSession, org_id: int):
  user_id = ctx.get_metadata("user_id")

  role = await OrganizationDAO.get_role_or_none(session, org_id, user_id)
  if role is None:
    raise ProtocolError('Нет прав')

  org = await OrganizationDAO.get_one(session, org_id, members=True)

  return (await org.to_dict(session=session, load_members=True)) | {
    'access_role': role
  }

class CreateOrgRequest(proto_models.BaseModel):
  name: str = Field(..., max_length=32)

@route.on('org/create', require_auth=True, ignore_params=['session'])
@database.connection
async def org_create(ctx: ConnectionContext, session: AsyncSession, req: CreateOrgRequest):
  user_id = ctx.get_metadata("user_id")
  user = await UserDAO.get_user(session, user_id)
  owned_org_count = await OrganizationDAO.owned_count(session, user_id)

  if owned_org_count >= user.organization_limit:
    raise ProtocolError('Вы создали максимальное количество организаций')

  org = await OrganizationDAO.create(session, user_id, req.name)
  await session.commit()

  return (await org.to_dict()) | {'access_role': 'owner'}


class RenameOrgRequest(proto_models.BaseModel):
  org_id: int
  name: str = Field(..., max_length=32)
@route.on('org/rename', require_auth=True, ignore_params=['session'])
@database.connection
async def org_rename(ctx: ConnectionContext, session: AsyncSession, req: RenameOrgRequest):
  user_id = ctx.get_metadata("user_id")

  await assert_role_at_least(session, req.org_id, user_id, OrganizationRole.ADMIN)

  await OrganizationDAO.rename(session, req.org_id, req.name)


async def assert_role_at_least(
    session: AsyncSession,
    org_id: int,
    user_id: int,
    min_role: OrganizationRole
) -> OrganizationRole:
  """
  Проверяет, что у пользователя в организации роль не ниже `min_role`.
  Порядок ролей: owner > admin > member.
  """
  order = {'owner': 3, 'admin': 2, 'member': 1, None: 0}
  role = await OrganizationDAO.get_role_or_none(session, org_id, user_id)
  if order.get(role, 0) < order[min_role.value]:
    raise ProtocolError('Нет прав')
  return role  # возврат фактической роли (owner или admin)


@route.on('org/members/kick', require_auth=True, ignore_params=['session'])
@database.connection
async def org_kick(
    ctx: ConnectionContext,
    session: AsyncSession,
    org_id: int,
    username: str
):
  user_id = ctx.get_metadata('user_id')
  user_role = await assert_role_at_least(session, org_id, user_id, OrganizationRole.ADMIN)

  target_id = await UserDAO.get_id_by_name(session, username)
  target_role = await OrganizationDAO.get_role_or_none(session, org_id, target_id)

  if target_id == user_id:
    raise ProtocolError('Нельзя кикнуть себя')

  # Админ не может кикнуть равного по роли (owner может кикнуть админа/мембера)
  if user_role == target_role:
    raise ProtocolError('Нельзя кикнуть равного пользователя')

  await OrganizationDAO.kick(session, org_id, target_id)
  await session.commit()

  async def notify_user():
    async with database.get_db() as notify_session:
      org_name = await OrganizationDAO.get_org_field(notify_session, org_id, 'name')
      await PushService.send_to_user(
        notify_session, target_id,
        'Вас кикнули',
        f'{ctx.get_metadata("username")} кикнул(а) вас из организации "{org_name}"'
      )

  asyncio.create_task(notify_user())

@route.on('org/leave', require_auth=True, ignore_params=['session'])
@database.connection
async def org_leave(
    ctx: ConnectionContext,
    session: AsyncSession,
    org_id: int
):
  user_id = ctx.get_metadata('user_id')
  user_role = await OrganizationDAO.get_role_or_none(session, org_id, user_id)

  if not user_role:
    raise ProtocolError('Вас нет в этой организации')

  if user_role == 'owner':
    raise ProtocolError('Вы не можете покинуть организацию. Передайте её кому-нибудь либо удалите.')

  await OrganizationDAO.kick(session, org_id, user_id)
  await session.commit()

class SetRoleRequest(proto_models.BaseModel):
  org_id: int
  username: str
  role: OrganizationRole


@route.on('org/members/set_role', require_auth=True, ignore_params=['session'])
@database.connection
async def org_set_role(
    ctx: ConnectionContext,
    session: AsyncSession,
    req: SetRoleRequest
):
  if ctx.get_metadata('username') == req.username:
    raise ProtocolError('Нельзя поменять себе роль')
  await assert_role_at_least(session, req.org_id, ctx.get_metadata('user_id'), OrganizationRole.OWNER)
  target_id = await UserDAO.get_id_by_name(session, req.username)
  if not target_id:
    raise ProtocolError('Пользователь не найден')
  await OrganizationDAO.set_role(session, req.org_id, target_id, req.role)

  await session.commit()


@route.on('org/members/add', require_auth=True, ignore_params=['session'])
@database.connection
async def org_add_user(
    ctx: ConnectionContext,
    session: AsyncSession,
    org_id: int,
    usernames: list[str]
):
  if ctx.get_metadata('username') in usernames:
    raise ProtocolError('Вы не можете добавить себя')
  await assert_role_at_least(session, org_id, ctx.get_metadata('user_id'), OrganizationRole.ADMIN)

  is_admin = not await UserDAO.is_admin(session, ctx.get_metadata('user_id'))
  count, limit = await OrganizationDAO.member_count_and_limit(session, org_id)

  for username in usernames:
    if count >= limit and not is_admin:
      raise ProtocolError('Превышен лимит пользователей')

    target_id = await UserDAO.get_id_by_name(session, username)

    if not target_id:
      raise ProtocolError('Пользователь не найден')

    if await OrganizationDAO.get_role_or_none(session, org_id, target_id):
      raise ProtocolError('Пользователь уже в организации')

    await OrganizationDAO.add_user(session, org_id, target_id)
  await session.commit()

  async def notify_user():
    async with database.get_db() as notify_session:
      org_name = await OrganizationDAO.get_org_field(notify_session, org_id, 'name')
      await PushService.send_to_user(
        notify_session, target_id,
        'Вас добавили в организацию',
        f'{ctx.get_metadata("username")} добавил(а) вас в организацию "{org_name}"'
      )

  asyncio.create_task(notify_user())
