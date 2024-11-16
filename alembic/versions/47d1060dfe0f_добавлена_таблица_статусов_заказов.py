"""Добавлена таблица статусов заказов

Revision ID: 47d1060dfe0f
Revises: ec5da340b795
Create Date: 2024-11-15 15:16:44.933738

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47d1060dfe0f'
down_revision: Union[str, None] = 'ec5da340b795'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
