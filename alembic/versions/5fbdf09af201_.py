"""empty message

Revision ID: 5fbdf09af201
Revises: cfc2ff93d043
Create Date: 2025-04-12 20:35:10.200446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5fbdf09af201'
down_revision: Union[str, None] = 'cfc2ff93d043'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('account', sa.Column('is_deleted', sa.Boolean(), server_default='0', nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('account', 'is_deleted')
    # ### end Alembic commands ###
