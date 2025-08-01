"""init

Revision ID: 72901fbd1cbf
Revises: 
Create Date: 2025-04-01 19:44:45.808800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72901fbd1cbf'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('currency',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=32), nullable=True),
    sa.Column('icon', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_currency_id'), 'currency', ['id'], unique=False)
    op.create_table('user',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=24), nullable=True),
    sa.Column('password', sa.String(length=256), nullable=True),
    sa.Column('joined_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_id'), 'user', ['id'], unique=False)
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=False)
    op.create_table('account',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('currency_id', sa.Integer(), nullable=True),
    sa.Column('account_number', sa.VARCHAR(length=6), nullable=True),
    sa.Column('balance', sa.DECIMAL(precision=19, scale=2), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['currency_id'], ['currency.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('account_number')
    )
    op.create_index(op.f('ix_account_currency_id'), 'account', ['currency_id'], unique=False)
    op.create_index(op.f('ix_account_id'), 'account', ['id'], unique=False)
    op.create_index(op.f('ix_account_user_id'), 'account', ['user_id'], unique=False)
    op.create_table('transaction',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('sender_account_id', sa.Integer(), nullable=True),
    sa.Column('recipient_account_id', sa.Integer(), nullable=True),
    sa.Column('amount', sa.DECIMAL(precision=19, scale=2), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['recipient_account_id'], ['account.id'], ),
    sa.ForeignKeyConstraint(['sender_account_id'], ['account.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_id'), 'transaction', ['id'], unique=False)
    op.create_index(op.f('ix_transaction_recipient_account_id'), 'transaction', ['recipient_account_id'], unique=False)
    op.create_index(op.f('ix_transaction_sender_account_id'), 'transaction', ['sender_account_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_transaction_sender_account_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_recipient_account_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_id'), table_name='transaction')
    op.drop_table('transaction')
    op.drop_index(op.f('ix_account_user_id'), table_name='account')
    op.drop_index(op.f('ix_account_id'), table_name='account')
    op.drop_index(op.f('ix_account_currency_id'), table_name='account')
    op.drop_table('account')
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_index(op.f('ix_user_id'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_currency_id'), table_name='currency')
    op.drop_table('currency')
    # ### end Alembic commands ###
