"""Add is_paid column to orders table

Revision ID: 24b1157d77c3
Revises: 7a142299d080
Create Date: 2025-01-26 12:35:57.171297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24b1157d77c3'
down_revision: Union[str, None] = '7a142299d080'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
