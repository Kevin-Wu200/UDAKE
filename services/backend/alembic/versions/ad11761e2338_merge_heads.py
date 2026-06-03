"""merge_heads

Revision ID: ad11761e2338
Revises: 20260416_0009, 20260507_0009
Create Date: 2026-05-09 16:30:03.762971
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'ad11761e2338'
down_revision: Union[str, None] = ('20260415_0008', '20260507_0009')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
