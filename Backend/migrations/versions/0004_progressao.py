"""progressao etapa 7

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default obrigatório: mesmo motivo de 0002/0003 (SQLite recusa
    # ADD COLUMN NOT NULL numa tabela com linhas existentes, ver ADR-0004).
    op.add_column('personagens', sa.Column('nivel', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('personagens', sa.Column('xp', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('personagens', 'xp')
    op.drop_column('personagens', 'nivel')
