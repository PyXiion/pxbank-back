from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.dialects.mysql import TEXT

from pxproto.database import Base


class WebPushSubscription(Base):
  __tablename__ = "webpush_subscription"

  id = Column(Integer, primary_key=True, index=True)
  user_id = Column(ForeignKey("user.id"), index=True,
                   nullable=False)  # ID пользователя (например, от системы аутентификации)
  endpoint = Column(TEXT, nullable=False)  # URL конечной точки подписки
  p256dh = Column(TEXT, nullable=False)  # Публичный ключ (p256dh)
  auth = Column(TEXT, nullable=False)  # Ключ аутентификации (auth)
