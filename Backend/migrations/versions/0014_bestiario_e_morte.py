"""bestiario e morte persistida - pendencias 3 e 4 do remaster UX

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, Sequence[str], None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('personagens', sa.Column('monstros_derrotados', sa.JSON(), nullable=True))
    op.add_column('personagens', sa.Column('morto_em', sa.DateTime(), nullable=True))
    op.add_column('personagens', sa.Column('pontuacao_final', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('personagens', 'pontuacao_final')
    op.drop_column('personagens', 'morto_em')
    op.drop_column('personagens', 'monstros_derrotados')
