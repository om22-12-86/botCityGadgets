"""Add status_history table and relationship

Revision ID: e6ee1ed5019b
Revises: f3469ebe3f0b
Create Date: 2024-11-15 15:58:49.527704

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6ee1ed5019b'
down_revision: Union[str, None] = 'f3469ebe3f0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
