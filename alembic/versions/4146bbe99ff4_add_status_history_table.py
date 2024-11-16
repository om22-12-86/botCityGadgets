"""Add status_history table

Revision ID: 4146bbe99ff4
Revises: bca0a6c6b2c7
Create Date: 2024-11-15 15:25:14.188316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4146bbe99ff4'
down_revision: Union[str, None] = 'bca0a6c6b2c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
