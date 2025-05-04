import decimal
import random

from sqlalchemy import func, or_
from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

import database
import models
from dao import AccountDAO, UserDAO
from dao.org import OrganizationDAO
from dao.push_service import PushService
from logger import logger
from proto_models import TransferBetweenModel, TransferByNumberModel
from pxws.connection_ctx import ConnectionContext
from pxws.error_with_data import ProtocolError
from pxws.route import Route

route = Route()


async def can_access_account(sess: AsyncSession, user: models.User, account: models.Account) -> bool:
  if user.is_admin or (account.user_id == user.id and not account.is_deleted):
    return True

  org_id = account.organization_id
  if org_id is not None:
    return await OrganizationDAO.get_role_or_none(sess, org_id, user.id) is not None

  return False


@route.on('accounts/fetch/user', require_auth=True)
async def fetch(ctx: ConnectionContext, id: str):
  async with database.get_db() as sess:
    # Проверка прав доступа
    user_id: int = ctx.get_metadata('user_id', None)
    is_admin = (await UserDAO.is_admin(sess, user_id)) if user_id else False

    target_user_id = await UserDAO.get_id_by_name(sess, id)
    if not target_user_id:
      raise ProtocolError("Пользователь не найден")

    stmt = (
      select(
        models.Account
      )
      .where(
        models.Account.user_id == target_user_id,
        or_(
          models.Account.is_public == True,
          models.Account.user_id == user_id,
          is_admin
        ),
        models.Account.is_deleted == False
      )
      .order_by(
        models.Account.list_order
      )
    )

    result = await sess.execute(stmt)

    # формирование ответа
    can_manage = target_user_id == user_id or is_admin
    accounts = []
    for acc in result.scalars():
      accounts.append(acc.to_dict() | {
        'can_manage': can_manage
      })

    return {
      'accounts': accounts
    }


@route.on('accounts/fetch/org', require_auth=True, ignore_params=['session'])
@database.connection
async def fetch_org(ctx: ConnectionContext, session: AsyncSession, id: int):
  # Проверка прав доступа
  user_id: int = ctx.get_metadata('user_id', None)
  is_admin = (await UserDAO.is_admin(session, user_id)) if user_id else False
  role = (await OrganizationDAO.get_role_or_none(session, id, user_id)) if id and user_id else None

  if role or is_admin:
    result = await OrganizationDAO.get_accounts_for_user(session, id, user_id)
  else:
    result = await OrganizationDAO.get_public_accounts(session, id)

  # формирование ответа
  can_manage = role or is_admin
  accounts = []
  for acc in result:
    accounts.append(acc.to_dict() | {
      'can_manage': can_manage
    })

  return {
    'accounts': accounts
  }


@route.on('accounts/new/user', require_auth=True, ignore_params=['session'])
@database.connection
async def create_user_account(session: AsyncSession, ctx: ConnectionContext, id: str, name: str,
                              currency_id: int):
  user = await UserDAO.get_user(session, ctx.get_metadata('user_id'))
  assert user

  if user.username != id and not user.is_admin:
    raise ProtocolError('Шо творишь, ирод. Прав нет')

  target_user = await UserDAO.get_user(session, id)
  assert target_user

  await _check_account_limit(session, user, target_user.id)

  acc = await AccountDAO.create(session, 'user', target_user.id, name, currency_id)
  await session.commit()

  return acc.to_dict() | {'can_manage': True}


@route.on('accounts/new/org', require_auth=True, ignore_params=['session'])
@database.connection
async def create_org_account(session: AsyncSession, ctx: ConnectionContext, id: int, name: str, currency_id: int):
  user = await UserDAO.get_user(session, ctx.get_metadata('user_id'))
  assert user

  if not user.is_admin:
    role = await OrganizationDAO.get_role_or_none(session, id, user.id)
    if role == 'member':
      raise ProtocolError('Шо творишь, ирод. Прав нет')

  await _check_account_limit(session, user, id, is_org=True)

  acc = await AccountDAO.create(session, 'org', id, name, currency_id)
  await session.commit()

  return acc.to_dict() | {'can_manage': True}


async def _check_account_limit(session: AsyncSession, user, owner_id: int, is_org: bool = False):
  if user.is_admin:
    return

  column = models.Account.organization_id if is_org else models.Account.user_id

  stmt = (
    select(func.count())
    .select_from(models.Account)
    .where(column == owner_id, models.Account.is_deleted == False)
  )

  account_count = (await session.execute(stmt)).scalar()
  limit = user.account_limit if not is_org else await OrganizationDAO.account_limit(session, owner_id)

  if account_count >= limit:
    raise ProtocolError('Вы достигли лимита счетов, которые можно открыть.')


@route.on('accounts/rename', require_auth=True, ignore_params=['session'])
@database.connection
async def rename(session: AsyncSession, ctx: ConnectionContext, account_id: int, new_name: str):
  user = await UserDAO.get_user(session, ctx.get_metadata('user_id'))
  account = await AccountDAO.get_account(session, account_id)

  if not account or not await can_access_account(session, user, account):
    raise ProtocolError('Доступ к счёту запрещён')

  account.name = new_name
  await session.commit()


@route.on('accounts/delete', require_auth=True, ignore_params=['session'])
@database.connection
async def delete(session: AsyncSession, ctx: ConnectionContext, account_id: int):
  user = await UserDAO.get_user(session, ctx.get_metadata('user_id'))
  account = await AccountDAO.get_account(session, account_id)

  if not account or not await can_access_account(session, user, account):
    raise ProtocolError('Доступ к счёту запрещён')

  if account.balance != 0:
    raise ProtocolError('Нельзя закрыть счёт с ненулевым балансом')

  account.is_deleted = True
  await session.commit()


@route.on('accounts/settings', require_auth=True, ignore_params=['session'])
@database.connection
async def settings(session: AsyncSession, ctx: ConnectionContext, account_id: int, is_public: bool):
  user = await UserDAO.get_user(session, ctx.get_metadata('user_id'))
  account = await AccountDAO.get_account(session, account_id, for_update=False)

  if not account or not await can_access_account(session, user, account):
    raise ProtocolError('Доступ к счёту запрещён')

  account.is_public = is_public
  await session.commit()


async def transfer(session: AsyncSession, author_id: int, comment: str, from_account: models.Account,
                   to_account: models.Account,
                   amount: float) -> models.Transaction:
  if from_account.currency_id != to_account.currency_id:
    raise ProtocolError('У счетов разная валюта')

  if from_account.balance < amount:
    raise ProtocolError('Недостаточно средств')

  amount = decimal.Decimal(amount)

  from_account.balance -= amount
  to_account.balance += amount

  transaction = models.Transaction(
    sender_account_id=from_account.id,
    recipient_account_id=to_account.id,
    author_id=author_id,
    amount=amount,
    comment=comment
  )
  session.add(transaction)
  await session.flush()

  # Попытка уведомить получателя
  if from_account.user_id != to_account.user_id:
    await send_top_up_notification(
      session,
      to_account.user_id,
      from_account,
      to_account,
      transaction
    )

  return transaction


async def validate_transfer_amount(amount: float):
  if amount <= 0:
    raise ProtocolError('Сумма должна быть больше нуля')


async def get_current_user(session: AsyncSession, ctx: ConnectionContext) -> models.User:
  user_id = ctx.get_metadata('user_id')
  user = await UserDAO.get_user(session, user_id)
  if not user:
    raise ProtocolError('Пользователь не найден')
  return user


async def validate_accounts_access(
    session: AsyncSession,
    user: models.User,
    *accounts: models.Account
) -> bool:
  checks = [await can_access_account(session, user, acc) for acc in accounts]
  return all(checks)


async def get_transaction_payload(
    session: AsyncSession,
    transaction: models.Transaction,
    sender: models.Account,
    receiver: models.Account,
    current_user: models.User
) -> dict:
  from_account_id = sender.id if await can_access_account(session, current_user, sender) else None
  to_account_id = receiver.id if await can_access_account(session, current_user, receiver) else None

  return transaction.to_dict(
    sender_name=sender.user.username if sender.user else sender.organization.name,
    receiver_name=receiver.user.username if receiver.user else receiver.organization.name,
    currency_id=sender.currency_id,
    from_account_id=from_account_id,
    to_account_id=to_account_id,
    to_account_number=receiver.account_number,
    from_account_number=sender.account_number
  )


@route.on('accounts/transfer', require_auth=True, ignore_params=['session'])
@database.connection
async def transfer_between(session: AsyncSession, ctx: ConnectionContext,
                           data: TransferBetweenModel):
  # logger.info(f'accounts/transfer ')
  await validate_transfer_amount(data.amount)
  user = await get_current_user(session, ctx)

  from_account = await AccountDAO.get_account(session, data.from_account_id, get_user=True, get_org=True)
  to_account = await AccountDAO.get_account(session, data.to_account_id, get_user=True, get_org=True)

  if not from_account or not to_account or not await validate_accounts_access(session, user, from_account, to_account):
    raise ProtocolError('Операция невозможна')

  transaction = await transfer(session, user.id, data.comment, from_account, to_account, data.amount)
  await session.commit()

  return await get_transaction_payload(session, transaction, from_account, to_account, user)


@route.on('accounts/transfer/by_number', require_auth=True, ignore_params=['session'])
@database.connection
async def transfer_between_by_number(session: AsyncSession, ctx: ConnectionContext,
                                     data: TransferByNumberModel):
  await validate_transfer_amount(data.amount)
  user = await get_current_user(session, ctx)

  from_account = await AccountDAO.get_account(session, data.from_account_id, get_user=True, get_org=True)
  to_account = await AccountDAO.get_account(session, str(data.to_account_number), get_user=True, get_org=True)

  if not from_account or not to_account or not await can_access_account(session, user, from_account):
    raise ProtocolError('Операция невозможна')

  transaction = await transfer(session, user.id, data.comment, from_account, to_account, data.amount)
  payload = await get_transaction_payload(session, transaction, from_account, to_account, user)

  await session.commit()

  return payload


async def send_top_up_notification(
    session: AsyncSession,
    target_user_id: int,
    from_account: models.Account,
    to_account: models.Account,
    transaction: models.Transaction
):
  await PushService.send_to_user(
    session,
    target_user_id,
    f'Перевод на № {to_account.account_number}',
    f'{from_account.user.username if from_account.user else from_account.organization.name} (№ {from_account.account_number}) перевел(а) вам {transaction.amount:.2f}'
  )
