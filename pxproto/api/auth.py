import os
from datetime import timedelta, datetime

import bcrypt
from jose import jwt, JWTError, ExpiredSignatureError
from sqlalchemy import select

import database
import models
from pxws.connection_ctx import ConnectionContext
from pxws.error_with_data import ErrorWithData, ProtocolError
from pxws.route import Route
from utils import send_toast

JWT_SECRET: str = os.getenv("JWT_SECRET")
JWT_EXPIRATION_PERIOD = timedelta(seconds=int(os.getenv("JWT_EXPIRATION_PERIOD")))
JWT_REFRESH_EXPIRATION_PERIOD = timedelta(seconds=int(os.getenv("JWT_REFRESH_EXPIRATION_PERIOD")))
JWT_ALGORITHM = "HS256"

assert JWT_SECRET is not None

def encode_jwt(data: dict, expiration_delta: timedelta) -> any:
  to_encode = data
  to_encode.update({'exp': datetime.now() + expiration_delta})
  return jwt.encode(to_encode, key=JWT_SECRET,algorithm="HS256")

def decode_jwt(token: str):
  return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


route = Route()

class TokenExpiredError(ErrorWithData):
  def __init__(self):
    ErrorWithData.__init__(self, 'Токен сессии истёк', {
      'reason': 'token expired'
    })

def get_hashed_password(password: str):
  return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password: str, hashed_password):
  return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

@route.on('auth')
async def auth(ctx: ConnectionContext, token: str):
  try:
    payload = decode_jwt(token)
    user_id = payload.get('user_id')

    if not user_id:
      raise ProtocolError("Invalid token: missing user_id")

    async with database.get_db() as sess:
      user = (await sess.execute(
        select(models.User).where(models.User.id == user_id)
      )).scalar_one_or_none()

      if not user:
        raise ProtocolError("User not found")

      ctx.set_authenticated({
        'user_id': user.id,
        'authenticated_at': datetime.utcnow().isoformat()
      })

      # Дополнительные метаданные
      ctx.set_metadata('user_id', user.id)
      ctx.set_metadata('username', user.username)

      await send_toast(ctx, 'info', 'Вы вошли в систему!', None, 3000)

      return {
        'username': user.username,
        'is_admin': user.is_admin,

        'exp': payload['exp']
      }

  except ExpiredSignatureError:
    raise TokenExpiredError()
  except JWTError as e:
    raise ProtocolError(f"Invalid token: {str(e)}")


def create_tokens(user_id: int) -> dict:
  """Генерация новой пары токенов"""
  access_payload = {
    'user_id': user_id,
    'exp': datetime.utcnow() + JWT_EXPIRATION_PERIOD,
    'type': 'access'
  }

  refresh_payload = {
    'user_id': user_id,
    'exp': datetime.utcnow() + JWT_REFRESH_EXPIRATION_PERIOD,
    'type': 'refresh'
  }

  return {
    'token': jwt.encode(access_payload, JWT_SECRET, algorithm=JWT_ALGORITHM),
    'refresh_token': jwt.encode(refresh_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
  }


@route.on('auth/login')
async def login(username: str, password: str):
  async with database.get_db() as sess:
    user = (await sess.execute(
      select(models.User).where(models.User.username == username)
    )).scalar_one_or_none()

    if not user or not check_password(password, user.password):
      raise ProtocolError("Неверные данные")

    return create_tokens(user.id)


@route.on('auth/refresh')
@route.require_auth
async def refresh(ctx: ConnectionContext, refresh_token: str):
  try:
    payload = decode_jwt(refresh_token)

    if payload.get('type') != 'refresh':
      raise ProtocolError("Неверный тип токена")

    user_id = payload.get('user_id')
    if not user_id:
      raise ProtocolError("Отсутствует user_id в токене")

    return create_tokens(user_id)

  except JWTError as e:
    raise ProtocolError(f"Invalid refresh token: {str(e)}")

@route.on('auth/update_password')
@route.require_auth
async def update_password(ctx: ConnectionContext, old_password: str, new_password: str):
  async with database.get_db() as sess:
    user = (await sess.execute(
      select(models.User).where(models.User.id == ctx.get_metadata('user_id'))
    )).scalar_one_or_none()

    if not user:
      raise ProtocolError("Пользователь не найден")

    if not check_password(old_password, user.password):
      raise ProtocolError("Неверный пароль")

    user.password = get_hashed_password(new_password)
    await sess.commit()
