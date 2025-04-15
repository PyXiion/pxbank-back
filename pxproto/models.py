import decimal
from datetime import datetime

import sqlalchemy
from sqlalchemy import Column, Integer, String, Table, ForeignKey, DateTime, Boolean, Enum, func, text, DECIMAL, VARCHAR
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import TEXT
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession

import proto_models
from pxproto.database import Base
import enum


class User(Base):
  __tablename__ = "user"

  id = Column(Integer, primary_key=True, index=True, autoincrement=True)
  username = Column(String(24), index=True)
  password = Column(String(256))

  is_admin = Column(Boolean, default=False, server_default='0')
  account_limit = Column(Integer, server_default='3')

  joined_at = Column(DateTime, default=datetime.utcnow)
  updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

  def set_password(self, new_password: str):
    from api.auth import get_hashed_password
    self.password = get_hashed_password(new_password)

class Currency(Base):
  __tablename__ = "currency"

  id = Column(Integer, primary_key=True, index=True, autoincrement=True)

  name = Column(String(32))
  icon = Column(String(32))


class Account(Base):
  __tablename__ = "account"

  id = Column(Integer, primary_key=True, index=True, autoincrement=True)
  user_id = Column(ForeignKey("user.id"), index=True)
  currency_id = Column(ForeignKey("currency.id"), index=True)

  name = Column(VARCHAR(30))
  list_order = Column(Integer, index=True)
  account_number = Column(VARCHAR(6), index=True, unique=True)

  balance: decimal.Decimal = Column(DECIMAL(19, 2), default=0.0)

  created_at = Column(DateTime, default=datetime.utcnow)
  updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
  is_deleted = Column(Boolean, server_default='0', default=False)

  user = relationship("User", backref="accounts")

  def to_dict(self):
    return {
      'id': self.id,
      'name': self.name,
      'order_id': self.list_order,
      'currency_id': self.currency_id,
      'balance': float(self.balance),
      'number': self.account_number
    }


class TransactionStatus(enum.Enum):
  PENDING = 0
  FAILED = 1
  COMPLETED = 2


class Transaction(Base):
  __tablename__ = "transaction"

  id = Column(Integer, primary_key=True, index=True, autoincrement=True)
  author_id = Column(ForeignKey("user.id"), index=True)

  sender_account_id = Column(ForeignKey("account.id"), index=True)
  recipient_account_id = Column(ForeignKey("account.id"), index=True)

  amount = Column(DECIMAL(19, 2))

  created_at = Column(DateTime, default=datetime.utcnow)

  def to_dict(self, *,
              sender_name: str,
              receiver_name: str,
              currency_id: int,
              from_account_id: int = None,
              to_account_id: int = None,
              from_account_number: int,
              to_account_number: int):
    data = {
      'id': self.id,
      'amount': float(self.amount),
      'sender_name': sender_name,
      'receiver_name': receiver_name,
      'currency_id': currency_id,
      'from_account_id': from_account_id,
      'to_account_id': to_account_id,
      'timestamp': self.created_at.timestamp(),
      'from_account_number': from_account_number,
      'to_account_number': to_account_number
    }
    return {k: v for k, v in data.items() if v is not None}


class WebPushSubscription(Base):
  __tablename__ = "webpush_subscription"

  id = Column(Integer, primary_key=True, index=True)
  user_id = Column(ForeignKey("user.id"), index=True, nullable=False)  # ID пользователя (например, от системы аутентификации)
  endpoint = Column(TEXT, nullable=False)  # URL конечной точки подписки
  p256dh = Column(TEXT, nullable=False)  # Публичный ключ (p256dh)
  auth = Column(TEXT, nullable=False)  # Ключ аутентификации (auth)