import json
import os

import aiohttp
import webpush, webpush.types
from webpush import WebPush
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import database
from .dao import BaseDAO
from models import WebPushSubscription

VAPID_PRIVATE_CERT = os.getenv("VAPID_PRIVATE_CERT")
VAPID_PUBLIC_CERT = os.getenv("VAPID_PUBLIC_CERT")

wp = WebPush(
  private_key=VAPID_PRIVATE_CERT.encode('utf-8'),
  public_key=VAPID_PUBLIC_CERT.encode('utf-8'),
  subscriber='me@pyxiion.ru'
)

class PushService(BaseDAO[WebPushSubscription]):
  model = WebPushSubscription

  @classmethod
  async def subscribe(
      cls,
      session: AsyncSession,
      user_id: int,
      endpoint: str,
      p256dh: str,
      auth: str
  ):
    sub = cls.model(
      user_id=user_id,
      endpoint=endpoint,
      p256dh=p256dh,
      auth=auth
    )
    session.add(sub)
    await session.commit()
    return sub

  @classmethod
  async def sub_exists(cls, session: AsyncSession, id: int):
    stmt = select(cls.model).filter_by(id=id)
    result = await session.execute(stmt)
    return bool(result.scalar_one_or_none())

  @classmethod
  async def send_to_user(cls, session: AsyncSession, user_id: int, title: str, body: str):
    stmt = select(cls.model).filter_by(user_id=user_id)
    subs = await session.execute(stmt)

    data = json.dumps({
      'title': title,
      'body': body
    })

    async with aiohttp.ClientSession() as client:
      for sub in subs.scalars().all():
        msg = wp.get(data, webpush.WebPushSubscription(
          endpoint=sub.endpoint,
          keys=webpush.types.WebPushKeys(
            auth=sub.auth,
            p256dh=sub.p256dh
          )
        ))
        await client.post(
          url=sub.endpoint,
          data=msg.encrypted,
          headers=msg.headers
        )