"""temperamento_mestre, dificuldade e resumo_historia - remaster da criacao de personagem

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, Sequence[str], None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'personagens',
        sa.Column('temperamento_mestre', sa.String(), nullable=False, server_default='Justo'),
    )
    op.add_column(
        'personagens',
        sa.Column('dificuldade', sa.String(), nullable=False, server_default='Normal'),
    )
    # Fase 2 do remaster de criação (Oráculo) — frase-gancho curta usada em
    # todo turno no lugar do corte cru de historia_texto[:150]. Nula para
    # personagens antigos e para quem não passou pelo Oráculo.
    op.add_column(
        'personagens',
        sa.Column('resumo_historia', sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('personagens', 'resumo_historia')
    op.drop_column('personagens', 'dificuldade')
    op.drop_column('personagens', 'temperamento_mestre')
