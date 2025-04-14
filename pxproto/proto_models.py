import datetime
from typing import Optional
from enum import IntEnum

from pydantic import BaseModel, field_validator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  import models

class JwtToken(BaseModel):
  user_id: int