"""equipamento - slots de arma, armadura e escudo (Fase 1 do plano "jogo completo", ADR-0033)

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0016'
down_revision: Union[str, Sequence[str], None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Coluna própria (não JSON dentro de world_state) porque é ficha: aparece
    # na Home/ficha e é lida por combat.escolher_arma, que não recebe o
    # world_state. Saves antigos nascem com {} e services/items.auto_equipar
    # preenche na primeira carga.
    op.add_column(
        'personagens',
        sa.Column('equipamento', sa.JSON(), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('personagens', 'equipamento')
