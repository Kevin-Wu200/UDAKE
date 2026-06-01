"""merge ip security and ticket branches

Revision ID: 30c2b4c024e1
Revises: 20260601_0011, 4ba19ae9e84f
Create Date: 2026-06-01 12:02:02.218219
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30c2b4c024e1'
down_revision: Union[str, None] = ('20260601_0011', '4ba19ae9e84f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
