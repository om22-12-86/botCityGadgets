"""Добавлены связи для OrderItem

Revision ID: f3469ebe3f0b
Revises: 700a1b503f6d
Create Date: 2024-11-15 15:33:26.449172

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3469ebe3f0b'
down_revision: Union[str, None] = '700a1b503f6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
