"""merge_langgraph_and_46

Revision ID: d4b933e25f62
Revises: 20250101_langgraph, 46
Create Date: 2026-01-01 22:04:20.179125

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b933e25f62'
down_revision: Union[str, None] = ('20250101_langgraph', '46')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
