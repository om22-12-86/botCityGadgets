"""Add payment fields to Order

Revision ID: 8e2cfe36f9eb
Revises: 63674a27c09e
Create Date: 2025-01-26 12:03:31.090481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e2cfe36f9eb'
down_revision: Union[str, None] = '63674a27c09e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('is_paid', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('orders', sa.Column('receipt_url', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'is_paid')
    op.drop_column('orders', 'receipt_url')
