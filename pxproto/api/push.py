import os

from sqlalchemy.ext.asyncio import AsyncSession

import database
from dao.push_service import PushService
from pxws.connection_ctx import ConnectionContext
from pxws.route import Route

PRIVATE = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY_B64_SAFE")

route = Route()


@route.on('push/key')
def get_key():
  return VAPID_PUBLIC_KEY


@route.on('push/subscribe', require_auth=True, ignore_params=['session'])
@database.connection
async def subscribe(ctx: ConnectionContext, endpoint: str, keys: any, *, session: AsyncSession):
  sub = await PushService.subscribe(
    session,
    ctx.get_metadata('user_id'),
    endpoint,
    keys['p256dh'],
    keys['auth']
  )
  return sub.id


@route.on('push/is_alive', require_auth=True, ignore_params=['session'])
@database.connection
async def is_alive(session: AsyncSession, id: int):
  return await PushService.sub_exists(session, id)
