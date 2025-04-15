from sqlalchemy.ext.asyncio import AsyncSession

import database
from dao import UserDAO
from pxws.connection_ctx import ConnectionContext
from pxws.error_with_data import ProtocolError
from pxws.route import Route

route = Route()

async def check_admin(session: AsyncSession, ctx: ConnectionContext):
  if not await UserDAO.is_admin(session, ctx.get_metadata('user_id')):
    raise ProtocolError('Ты куда лезешь')

@route.on('admin/new_user', require_auth=True, ignore_params=['session'])
@database.connection
async def new_user(session: AsyncSession, ctx: ConnectionContext, username: str, password: str):
  await check_admin(session, ctx)

  await UserDAO.create(session, username, password)

@route.on('admin/change_password', require_auth=True, ignore_params=['session'])
@database.connection
async def change_password(
    session: AsyncSession,
    ctx: ConnectionContext,
    username: str,
    password: str
):
  await check_admin(session, ctx)

  await UserDAO.set_password(session, username, password)
  await session.commit()
