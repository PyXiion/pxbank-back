from typing import Generic, Union, TypeVar, Optional

from pxproto.database import Base

T = TypeVar("T", bound=Base) # мы можем задать границу типа, т.о. мы будем уверены при статическом анализе что использованы верные типы как минимум в иерархии

class BaseDAO(Generic[T]):
  model: type[T]
