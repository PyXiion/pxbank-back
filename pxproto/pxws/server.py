import asyncio
import inspect
import json
import logging
import typing
from functools import wraps
from typing import Dict, Any, get_type_hints, get_origin, Optional, Union

from pydantic import BaseModel, ValidationError
from websockets import ConnectionClosed
from websockets.asyncio.server import serve
from websockets.server import ServerConnection

from .base_models import Request, ErrorResponse, SuccessResponse
from .connection_ctx import ConnectionContext
from .error_with_data import ErrorWithData, ProtocolError
from .handler import HandlerInfo, register_handler
from .logger import logger
from .route import Route

ConnectionHandlerType = typing.Callable[[ConnectionContext], typing.Coroutine[Any, Any, Any]]


class Server:
  def __init__(self):
    self._ws_server = None
    self._connections: Dict[ServerConnection, ConnectionContext] = {}
    self._handlers: Dict[str, HandlerInfo] = {}
    self._connection_handler: ConnectionHandlerType | None = None
    self._auth_validator: Optional[typing.Callable[[Any], typing.Coroutine[Any, Any, bool]]] = None

  async def serve_forever(self, host: str, port: int):
    self._ws_server = await serve(self._on_connection, host, port)
    await self._ws_server.serve_forever()

  def set_auth_validator(self, validator: typing.Callable[[Any], typing.Coroutine[Any, Any, bool]]):
    """Устанавливает функцию для проверки аутентификации"""
    self._auth_validator = validator

  def on(self, type_name: str, require_auth: bool = False):
    """Декоратор для регистрации обработчиков"""

    def decorator(func):
      return register_handler(self._handlers, type_name, func, require_auth)

    return decorator

  def require_auth(self, func):
    """Декоратор для пометки обработчика как требующего аутентификации"""
    for handler_type, handler_info in self._handlers.items():
      if handler_info['original_func'] == func:
        handler_info['require_auth'] = True
        break
    return func

  def add_route(self, route: Route) -> None:
    """Добавляет обработчики из route в сервер"""
    handlers = route.get_handlers()
    for type_name, handler_info in handlers.items():
      if type_name in self._handlers:
        logger.warning(f"Handler for type '{type_name}' already exists, overwriting")
      self._handlers[type_name] = handler_info
      logger.info(f"Added handler for '{type_name}' from route")

  async def _on_connection(self, connection: ServerConnection):
    ctx = ConnectionContext(self, connection)
    self._connections[connection] = ctx
    logger.info(f"New connection from {connection.remote_address[0]} ({connection.id}), total: {len(self._connections)}")

    try:
      if self._connection_handler:
        await self._connection_handler(ctx)

      async for message in connection:
        await self._on_message(ctx, message)
    except ConnectionClosed:
      logger.info("Connection closed")
    finally:
      self._connections.pop(connection, None)
      logger.info(f"Connection removed, total: {len(self._connections)}")

  async def _on_message(self, ctx: ConnectionContext, message: str):
    try:
      request_data = json.loads(message)
      request = Request(**request_data)

      logger.info(f"\"{request.type}\" from {ctx.connection.remote_address[0]} with id {request.id}")
      # logger.debug(f"")

      if request.type not in self._handlers:
        raise ValueError(f"No handler for type '{request.type}'")

      handler_info = self._handlers[request.type]
      handler = handler_info['original_func']  # Используем оригинальную функцию, а не обертку

      # Проверка аутентификации если требуется
      if handler_info['require_auth'] and not ctx.is_authenticated:
        raise ProtocolError("Требуется авторизация")

      # Подготовка аргументов для обработчика
      kwargs = {}
      if request.data is None:
        request.data = {}

      # Проверяем, ожидает ли обработчик контекст
      sig = inspect.signature(handler)
      if 'ctx' in sig.parameters:
        kwargs['ctx'] = ctx

      if not handler_info['is_single_param'] or not handler_info['has_pydantic_params']:
        # Случай 1: Есть несколько параметров или один простой
        # Ожидаем data в формате {param1: value1, param2: value2}
        for param_name in handler_info['expected_params']:
          if param_name not in request.data:
            raise ValueError(f"Missing parameter '{param_name}' in request data", handler)

          param_type = handler_info['type_hints'].get(param_name)
          if self._is_pydantic_model(param_type):
            kwargs[param_name] = param_type(**request.data[param_name])
          else:
            kwargs[param_name] = request.data[param_name]
      elif handler_info['has_pydantic_params']:
        # Случай 2: Один параметр-модель
        # Ожидаем data как значение этого параметра
        param_name = next(iter(handler_info['expected_params']))
        param_type = handler_info['type_hints'].get(param_name)
        if self._is_pydantic_model(param_type):
          kwargs[param_name] = param_type(**request.data)
        else:
          kwargs[param_name] = request.data

      # Вызов обработчика
      result = handler(**kwargs)

      if inspect.isawaitable(result):
        result = await result

      # Подготовка ответа
      response_model = handler_info['type_hints'].get('return')
      if response_model:
        response_data = self._prepare_response_data(result, response_model)
      else:
        response_data = result

      response = SuccessResponse(data=response_data, id=request.id)

      if ttl := ctx.get_metadata('ttl'):
        response.ttl = ttl
        ctx.set_metadata('ttl', None)

    except ErrorWithData as e:
      error_id = request.id if 'request' in locals() else 'unknown'
      response = ErrorResponse(error=e.message, id=error_id, data=e.data)
    except ProtocolError as e:
      error_id = request.id if 'request' in locals() else 'unknown'
      response = ErrorResponse(error=e.message, id=error_id)
    except ValidationError as e:
      error_id = request.id if 'request' in locals() else 'unknown'
      response = ErrorResponse(error='JSON validation error', id=error_id)
      logger.error(f"Validation error: {e}", exc_info=e)
    except Exception as e:
      error_id = request.id if 'request' in locals() else 'unknown'
      response = ErrorResponse(error='unknown error', id=error_id)
      logger.error(f"Error processing message: {e}", exc_info=e)

    await ctx.connection.send(response.json(exclude_none=True))

  async def disconnect_connection(self, ctx: ConnectionContext) -> None:
    """Отключает соединение"""
    await ctx.connection.close()
    self._connections.pop(ctx.connection, None)

  def _prepare_response_data(self, result, response_model):
    """Подготавливает данные ответа с учетом сложных типов"""
    # Если модель ответа не указана, возвращаем как есть
    if response_model is None:
      return result

    origin_type = get_origin(response_model) or response_model

    # Optional[Type]
    if origin_type is typing.Union:
      args = typing.get_args(response_model)
      if type(None) in args:  # Это Optional
        if result is None:
          return None
        actual_type = next(arg for arg in args if arg is not type(None))
        return self._prepare_response_data(result, actual_type)

    # list[Type]
    if origin_type in (list, typing.List) or isinstance(result, list):
      item_type = typing.get_args(response_model)[0] if get_origin(response_model) else None

      if item_type and self._is_pydantic_model(item_type):
        return [self._prepare_response_data(item, item_type) for item in result]
      return result

    # dict[K, V]
    if origin_type in (dict, Dict):
      key_type, val_type = typing.get_args(response_model)
      if self._is_pydantic_model(val_type):
        return {k: self._prepare_response_data(v, val_type) for k, v in result.items()}
      return result

    # Pydantic
    if self._is_pydantic_model(response_model):
      if isinstance(result, response_model):
        return result.dict(exclude_none=True)
      try:
        return response_model(**result).dict()
      except Exception as e:
        raise ValueError(f"Failed to convert result to {response_model}: {str(e)}")

    # Простые типы
    return result

  def _is_pydantic_model(self, type_) -> bool:
    """Проверяет, является ли тип моделью Pydantic"""
    try:
      return isinstance(type_, type) and issubclass(type_, BaseModel)
    except TypeError:
      return False

  @property
  def connections_it(self):
    return (v for _, v in self._connections.items())

