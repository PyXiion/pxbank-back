from sqlalchemy import or_, select, func
from sqlalchemy.orm import aliased

from models import Transaction, Account, User
from .dao import BaseDAO


class TransactionDAO(BaseDAO[Transaction]):
    model = Transaction

    @classmethod
    def _stmt_with_filter(cls, field_name: str, target_id: int):
        """
        Internal: builds a select stmt for transactions where sender or recipient
        account has field == target_id
        """
        SenderAcc = aliased(Account)
        RecAcc = aliased(Account)
        SenderUser = aliased(User)
        RecUser = aliased(User)

        field_sender = getattr(SenderAcc, field_name)
        field_recipient = getattr(RecAcc, field_name)

        return (
            select(
                cls.model,
                SenderAcc,
                RecAcc,
                # если пользователь не привязан, подставляем номер счета
                func.coalesce(SenderUser.username, SenderAcc.account_number)
                    .label('sender_name'),
                func.coalesce(RecUser.username, RecAcc.account_number)
                    .label('recipient_name'),
            )
            .join(SenderAcc, cls.model.sender_account_id == SenderAcc.id)
            .outerjoin(SenderUser, SenderAcc.user_id == SenderUser.id)
            .join(RecAcc, cls.model.recipient_account_id == RecAcc.id)
            .outerjoin(RecUser, RecAcc.user_id == RecUser.id)
            .where(
                or_(
                    field_sender == target_id,
                    field_recipient == target_id,
                )
            )
            .order_by(cls.model.created_at.desc())
        )

    @classmethod
    def get_user_transactions_stmt(cls, user_id: int):
        """
        Returns stmt of transactions for given user_id on account.user_id
        """
        return cls._stmt_with_filter('user_id', user_id)

    @classmethod
    def get_org_transactions_stmt(cls, org_id: int):
        """
        Returns stmt of transactions for given org_id on account.organization_id
        """
        return cls._stmt_with_filter('organization_id', org_id)
