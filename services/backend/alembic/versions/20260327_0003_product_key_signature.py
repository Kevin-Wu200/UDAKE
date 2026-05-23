"""add product key signature column

Revision ID: 20260327_0003
Revises: 20260327_0002
Create Date: 2026-03-27 12:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260327_0003"
down_revision: Union[str, None] = "20260327_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product_keys", sa.Column("signature", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("product_keys", "signature")
