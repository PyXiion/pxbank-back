from typing import Any, Tuple

from sqlalchemy import select, func, Select
from sqlalchemy.ext.asyncio import AsyncSession

import database
from api.accounts import can_access_account
from dao import UserDAO
from dao.org import OrganizationDAO
from dao.transaction import TransactionDAO
from models import Transaction, User
from pxws.connection_ctx import ConnectionContext
from pxws.error_with_data import ProtocolError
from pxws.route import Route

route = Route()


async def prepare_transaction_response(
    session: AsyncSession,
    stmt: Select[tuple[Transaction, Any, Any, Any, Any]],
    page: int,
    current_user: User
) -> Tuple[list, int, int, int]:
  # Пагинация
  per_page = 10
  offset = (page - 1) * per_page

  count_stmt = select(func.count()).select_from(stmt.subquery())
  total = (await session.execute(count_stmt)).scalar_one()
  total_pages = (total + per_page - 1) // per_page

  result = await session.execute(stmt.limit(per_page).offset(offset))
  rows = result.all()

  transactions = []
  for tx, sender_acc, recipient_acc, sender_name, recipient_name in rows:
    from_access = await can_access_account(session, current_user, sender_acc)
    to_access = await can_access_account(session, current_user, recipient_acc)

    transactions.append(
      tx.to_dict(
        sender_name=sender_name,
        receiver_name=recipient_name,
        currency_id=sender_acc.currency_id,
        from_account_id=sender_acc.id if from_access else None,
        to_account_id=recipient_acc.id if to_access else None,
        from_account_number=sender_acc.account_number if from_access else None,
        to_account_number=recipient_acc.account_number if to_access else None,
      )
    )
  return transactions, total_pages, total, per_page


@route.on('transactions/fetch/user', require_auth=True, ignore_params=['session'])
@database.connection
async def fetch_transactions(
    session: AsyncSession,
    ctx: ConnectionContext,
    username: str,
    page: int = 1
):
  current_user_id = ctx.get_metadata('user_id')
  current_user = await UserDAO.get_user(session, current_user_id)
  is_admin = current_user.is_admin

  # Получаем целевого пользователя
  target_user = await UserDAO.get_user(session, username)
  if not target_user:
    raise ProtocolError('Пользователь не найден')

  # Проверка прав доступа
  if target_user.id != current_user_id and not is_admin:
    raise ProtocolError('Доступ к транзакциям других пользователей запрещён')

  # Строим запрос
  stmt = TransactionDAO.get_user_transactions_stmt(target_user.id)

  # Получаем данные с пагинацией и проверкой доступа к аккаунтам
  transactions, total_pages, total, per_page = await prepare_transaction_response(
    session, stmt, page, current_user
  )

  return {
    'transactions': transactions,
    'total_pages': total_pages,
    'total': total,
    'per_page': per_page,
  }


@route.on('transactions/fetch/org', require_auth=True, ignore_params=['session'])
@database.connection
async def fetch_org_transactions(
    session: AsyncSession,
    ctx: ConnectionContext,
    org_id: int,
    page: int = 1
):
  current_user_id = ctx.get_metadata('user_id')
  current_user = await UserDAO.get_user(session, current_user_id)
  is_admin = current_user.is_admin
  role = await OrganizationDAO.get_role_or_none(session, org_id, current_user_id)

  # Проверка прав доступа
  if not (role or is_admin):
    raise ProtocolError('Доступ к транзакциям других организаций запрещён')

  # Строим запрос
  stmt = TransactionDAO.get_org_transactions_stmt(org_id)

  # Получаем данные с пагинацией и проверкой доступа к аккаунтам
  transactions, total_pages, total, per_page = await prepare_transaction_response(
    session, stmt, page, current_user
  )

  return {
    'transactions': transactions,
    'total_pages': total_pages,
    'total': total,
    'per_page': per_page,
  }
