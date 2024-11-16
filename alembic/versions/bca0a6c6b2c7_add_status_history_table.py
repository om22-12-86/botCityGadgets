"""Add status_history table

Revision ID: bca0a6c6b2c7
Revises: 47d1060dfe0f
Create Date: 2024-11-15 15:21:34.925043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bca0a6c6b2c7'
down_revision: Union[str, None] = '47d1060dfe0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
