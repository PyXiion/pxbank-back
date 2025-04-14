import inspect
import typing
from functools import wraps

from pydantic import BaseModel

from pxws.logger import logger


class HandlerInfo(typing.TypedDict):
  handler: typing.Callable
  original_func: typing.Callable
  expected_params: dict[str, type]
  type_hints: dict[str, typing.Any]
  has_pydantic_params: bool
  is_single_param: bool
  require_auth: bool


def register_handler(
  handlers_dict: typing.Dict[str, HandlerInfo],
  type_name: str,
  func: typing.Callable,
  require_auth: bool = False,
  ignore_params: list[str] = None
) -> typing.Callable:
  """Общая функция для регистрации обработчиков"""

  @wraps(func)
  async def wrapper(*args, **kwargs):
    return await func(*args, **kwargs)

  sig = inspect.signature(func)
  type_hints = typing.get_type_hints(func)
  parameters = sig.parameters

  ignore_params = ignore_params if ignore_params else []

  expected_params = {
    name: param
    for name, param in parameters.items()
    if name not in ['request_type', 'request_id', 'ctx'] and name not in ignore_params
  }

  has_pydantic_params = any(
    isinstance(type_, type) and issubclass(type_, BaseModel)
    for type_ in type_hints.values()
  )

  # metadata
  handlers_dict[type_name] = {
    'handler': wrapper,
    'original_func': func,
    'expected_params': expected_params,
    'type_hints': type_hints,
    'has_pydantic_params': has_pydantic_params,
    'is_single_param': len(expected_params) == 1,
    'require_auth': require_auth,
  }

  logger.info(f"Registered handler for '{type_name}' with params: {expected_params}")
  return wrapper
