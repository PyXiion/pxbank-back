"""empty message

Revision ID: bedf1890ca0e
Revises: 43ba378f2dc4
Create Date: 2025-04-13 18:10:15.287106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bedf1890ca0e'
down_revision: Union[str, None] = '43ba378f2dc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('transaction', sa.Column('author_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_transaction_author_id'), 'transaction', ['author_id'], unique=False)
    op.create_foreign_key(None, 'transaction', 'user', ['author_id'], ['id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'transaction', type_='foreignkey')
    op.drop_index(op.f('ix_transaction_author_id'), table_name='transaction')
    op.drop_column('transaction', 'author_id')
    # ### end Alembic commands ###
