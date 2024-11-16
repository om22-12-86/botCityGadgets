"""Добавлены связи для OrderItem

Revision ID: 700a1b503f6d
Revises: 4146bbe99ff4
Create Date: 2024-11-15 15:32:24.793619

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '700a1b503f6d'
down_revision: Union[str, None] = '4146bbe99ff4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
