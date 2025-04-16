from typing import Optional
from typing import TYPE_CHECKING

from pydantic import BaseModel, constr

from config import TRANSACTION_COMMENT_MAX_LENGTH

if TYPE_CHECKING:
  pass


class TransferBaseModel(BaseModel):
  from_account_id: int

  amount: float
  comment: Optional[constr(max_length=TRANSACTION_COMMENT_MAX_LENGTH)] = None

class TransferByNumberModel(TransferBaseModel):
  to_account_number: str

class TransferBetweenModel(TransferBaseModel):
  to_account_id: int