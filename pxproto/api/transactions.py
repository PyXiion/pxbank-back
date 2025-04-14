from sqlalchemy import select, or_, func
from sqlalchemy.orm import aliased

import database
import models
import utils
from api.accounts import can_access_account
from dao import UserDAO
from pxws.connection_ctx import ConnectionContext
from pxws.error_with_data import ProtocolError
from pxws.route import Route

route = Route()


@route.on('transactions/fetch', require_auth=True)
async def fetch_transactions(ctx: ConnectionContext, username: str, page: int):
  async with database.get_db() as sess:
    # Получаем текущего пользователя
    current_user_id: int = ctx.get_metadata('user_id')
    current_user = await UserDAO.get_user(sess, current_user_id)
    is_admin = await UserDAO.is_admin(sess, current_user_id)

    # Целевой пользователь по имени
    target_user = await UserDAO.get_user(sess, username)
    if not target_user:
      raise ProtocolError("Пользователь не найден")

    if target_user.id != current_user_id and not is_admin:
      raise ProtocolError("Доступ к транзакциям других пользователей запрещён")

    # Алиасы
    sender_account = aliased(models.Account)
    recipient_account = aliased(models.Account)
    sender_user = aliased(models.User)
    recipient_user = aliased(models.User)

    stmt = (
      select(
        models.Transaction,
        sender_account,
        recipient_account,
        sender_user.username.label("sender_name"),
        recipient_user.username.label("recipient_name"),
      )
      .join(sender_account, models.Transaction.sender_account_id == sender_account.id)
      .join(sender_user, sender_account.user_id == sender_user.id)
      .join(recipient_account, models.Transaction.recipient_account_id == recipient_account.id)
      .join(recipient_user, recipient_account.user_id == recipient_user.id)
      .where(
        or_(
          sender_account.user_id == target_user.id,
          recipient_account.user_id == target_user.id,
        )
      )
      .order_by(models.Transaction.created_at.desc())
    )

    # Пагинация
    per_page = 10
    offset = (page - 1) * per_page

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await sess.execute(count_stmt)).scalar()
    total_pages = (total + per_page - 1) // per_page

    result = await sess.execute(stmt.limit(per_page).offset(offset))
    transactions_data = result.all()

    # Подготовка данных
    transactions = []
    for transaction, sender_acc, recipient_acc, sender_name, recipient_name in transactions_data:
      # Проверка доступа к каждой стороне
      from_access = await can_access_account(sess, current_user, sender_acc)
      to_access = await can_access_account(sess, current_user, recipient_acc)

      transactions.append(
        transaction.to_dict(
          sender_name=sender_name,
          receiver_name=recipient_name,
          currency_id=sender_acc.currency_id,
          from_account_id=sender_acc.id if from_access else None,
          to_account_id=recipient_acc.id if to_access else None,
          from_account_number=sender_acc.account_number,
          to_account_number=recipient_acc.account_number,
        )
      )

    return {
      "transactions": transactions,
      "total_pages": total_pages,
      "total": total,
      "per_page": per_page
    }
