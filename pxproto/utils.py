import json
from typing import Union, Optional, Literal

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Account
from pxws.connection_ctx import ConnectionContext


async def get_user_id_by_name(session: AsyncSession, username: str) -> Optional[int]:
  """Получает ID пользователя по его имени"""
  result = await session.execute(
    select(User.id).where(User.username == username)
  )
  user = result.scalar_one_or_none()
  return user


async def send_toast(
    ctx: ConnectionContext,
    severity: Literal['info', 'error', 'warn', 'success'],
    summary: Optional[str],
    detail: Optional[str],
    life: int
):
  await ctx.connection.send(json.dumps({
    'type': 'toast',
    'data': {
      'severity': severity,
      'summary': summary,
      'detail': detail,
      'life': life
    }
  }, ensure_ascii=False))
