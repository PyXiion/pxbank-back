from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

import database
from api.accounts import can_access_account
from dao import UserDAO
from dao.transaction import TransactionDAO
from models import Transaction
from pxws.connection_ctx import ConnectionContext
from pxws.error_with_data import ProtocolError
from pxws.route import Route

route = Route()


@route.on('transactions/fetch', require_auth=True, ignore_params=['session'])
@database.connection
async def fetch_transactions(session: AsyncSession, ctx: ConnectionContext, username: str, page: int):
  current_user_id: int = ctx.get_metadata('user_id')
  current_user = await UserDAO.get_user(session, current_user_id)
  is_admin = current_user.is_admin

  # Целевой пользователь по имени
  target_user = await UserDAO.get_user(session, username)
  if not target_user:
    raise ProtocolError("Пользователь не найден")

  if target_user.id != current_user_id and not is_admin:
    raise ProtocolError("Доступ к транзакциям других пользователей запрещён")

  stmt = TransactionDAO.get_user_transactions_with_accounts_stmt(target_user.id)

  # Пагинация
  per_page = 10
  offset = (page - 1) * per_page

  count_stmt = select(func.count()).select_from(stmt.subquery())
  total = (await session.execute(count_stmt)).scalar()
  total_pages = (total + per_page - 1) // per_page

  result = await session.execute(stmt.limit(per_page).offset(offset))
  transactions_data = result.all()

  transactions = []
  for transaction, sender_acc, recipient_acc, sender_name, recipient_name in transactions_data:
    transaction: Transaction
    from_access = await can_access_account(session, current_user, sender_acc)
    to_access = await can_access_account(session, current_user, recipient_acc)

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