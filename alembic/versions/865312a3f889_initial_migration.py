"""initial migration

Revision ID: 865312a3f889
Revises: 
Create Date: 2024-09-29 21:33:11.397722

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '865312a3f889'
down_revision: Union[str, None] = None
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

