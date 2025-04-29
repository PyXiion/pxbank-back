from sqlalchemy.ext.asyncio import AsyncSession

import database
from dao.org import OrganizationDAO
from pxws.connection_ctx import ConnectionContext
from pxws.route import Route

route = Route()


@route.on('org/fetch', require_auth=True, ignore_params=['session'])
@database.connection
async def fetch(ctx: ConnectionContext, session: AsyncSession):
  return await OrganizationDAO.get_user_organizations_with_roles(session, ctx.get_metadata('user_id'))