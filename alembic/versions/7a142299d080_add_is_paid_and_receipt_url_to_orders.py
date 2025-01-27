"""Add is_paid and receipt_url to orders

Revision ID: 7a142299d080
Revises: 8e2cfe36f9eb
Create Date: 2025-01-26 12:05:27.568783

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a142299d080'
down_revision: Union[str, None] = '8e2cfe36f9eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('is_paid', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('orders', sa.Column('receipt_url', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'is_paid')
    op.drop_column('orders', 'receipt_url')
