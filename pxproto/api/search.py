from sqlalchemy.ext.asyncio import AsyncSession

import database
from dao import UserDAO
from pxws.connection_ctx import ConnectionContext
from pxws.route import Route

route = Route()

@route.on('search/users', require_auth=True, ignore_params=['session'])
@database.connection
async def search_users(session: AsyncSession, username: str):
  return [
    x.username
    for x in await UserDAO.search_users(session, username)
  ]