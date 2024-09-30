"""Make description nullable in category

Revision ID: 79074999acf2
Revises: 865312a3f889
Create Date: 2024-09-29 21:42:18.377270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79074999acf2'
down_revision: Union[str, None] = '865312a3f889'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column('category', 'description',
                    existing_type=sa.String(),
                    server_default="")

def downgrade():
    op.alter_column('category', 'description',
                    existing_type=sa.String(),
                    server_default=None)

