from sqlalchemy import or_, select
from sqlalchemy.orm import aliased

from models import Transaction, Account, User
from .dao import BaseDAO

class TransactionDAO(BaseDAO[Transaction]):
  model = Transaction

  @classmethod
  def get_user_transactions_with_accounts_stmt(cls, target_user_id: int):
    """
    :return: stmt[transaction, sender_acc, recipient_acc, sender_name, recipient_name]
    """
    sender_account = aliased(Account)
    recipient_account = aliased(Account)
    sender_user = aliased(User)
    recipient_user = aliased(User)

    return (
      select(
        cls.model,
        sender_account,
        recipient_account,
        sender_user.username.label("sender_name"),
        recipient_user.username.label("recipient_name"),
      )
      .join(sender_account, cls.model.sender_account_id == sender_account.id)
      .join(sender_user, sender_account.user_id == sender_user.id)
      .join(recipient_account, cls.model.recipient_account_id == recipient_account.id)
      .join(recipient_user, recipient_account.user_id == recipient_user.id)
      .where(
        or_(
          sender_account.user_id == target_user_id,
          recipient_account.user_id == target_user_id,
        )
      )
      .order_by(cls.model.created_at.desc())
    )