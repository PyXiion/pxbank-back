from typing import Dict, get_type_hints

from pxws.handler import HandlerInfo, register_handler


class Route:
  """Класс для группировки обработчиков в отдельные модули"""

  def __init__(self):
    self._handlers: Dict[str, HandlerInfo] = {}

  def on(
      self, type_name: str,
      *,
      require_auth: bool = False,
      ignore_params: list[str] = None
  ):
    """Декоратор для регистрации обработчиков"""

    def decorator(func):
      return register_handler(self._handlers, type_name, func, require_auth, ignore_params)

    return decorator

  def require_auth(self, func):
    """Декоратор для пометки обработчика как требующего аутентификации"""
    for handler_type, handler_info in self._handlers.items():
      if handler_info['original_func'] == func:
        handler_info['require_auth'] = True
        break
    return func

  def get_handlers(self) -> Dict[str, HandlerInfo]:
    """Возвращает все обработчики этого route"""
    return self._handlers.copy()
