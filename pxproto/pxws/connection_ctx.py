import typing
from typing import Any, Optional, Dict

from websockets import ServerConnection

if typing.TYPE_CHECKING:
  from .server import Server


class ConnectionContext:
  """Контекст соединения для хранения метаданных, включая аутентификацию"""

  def __init__(self, server: "Server", connection: ServerConnection):
    self.server = server
    self.connection = connection
    self._authenticated = False
    self._auth_data: Optional[Any] = None
    self._metadata: Dict[str, Any] = {}

  @property
  def is_authenticated(self) -> bool:
    """Проверяет, аутентифицировано ли соединение"""
    return self._authenticated

  @property
  def auth_data(self) -> Optional[Any]:
    """Возвращает данные аутентификации"""
    return self._auth_data

  def set_authenticated(self, auth_data: Any = None) -> None:
    """Помечает соединение как аутентифицированное"""
    self._authenticated = True
    self._auth_data = auth_data

  def set_unauthenticated(self) -> None:
    """Помечает соединение как неаутентифицированное"""
    self._authenticated = False
    self._auth_data = None

  def set_metadata(self, key: str, value: Any) -> None:
    """Устанавливает метаданные соединения"""
    self._metadata[key] = value

  def get_metadata(self, key: str, default: Optional[Any] = None) -> Any:
    """Получает метаданные соединения"""
    return self._metadata.get(key, default)

  def __str__(self):
    return f'[ConnectionContext, is_authenticated:{self.is_authenticated}, meta: {self._metadata}]'