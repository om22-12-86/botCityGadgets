"""Allow null in category description

Revision ID: ec5da340b795
Revises: 79074999acf2
Create Date: 2024-09-29 21:47:51.338238

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec5da340b795'
down_revision: Union[str, None] = '79074999acf2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
