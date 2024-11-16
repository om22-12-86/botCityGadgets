"""Add price to order items

Revision ID: 63674a27c09e
Revises: e6ee1ed5019b
Create Date: 2024-11-15 16:20:34.847567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63674a27c09e'
down_revision: Union[str, None] = 'e6ee1ed5019b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
