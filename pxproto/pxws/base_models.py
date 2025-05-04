from typing import Optional, Any

from pydantic import BaseModel


class Request(BaseModel):
  type: str
  id: str
  data: Optional[Any] = None


class SuccessResponse(BaseModel):
  status: str = "ok"
  data: Any
  id: str
  ttl: Optional[float] = None


class ErrorResponse(BaseModel):
  status: str = "error"
  error: str
  id: str
  data: Optional[dict] = None