"""contas etapa 8

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Login por senha e/ou Google (ADR-0014) — nenhuma das duas colunas é
    # obrigatória sozinha, uma conta só precisa ter pelo menos uma.
    op.add_column('usuarios', sa.Column('senha_hash', sa.String(), nullable=True))
    op.add_column('usuarios', sa.Column('google_sub', sa.String(), nullable=True))
    op.create_index(op.f('ix_usuarios_google_sub'), 'usuarios', ['google_sub'], unique=True)

    # server_default obrigatório: SQLite recusa ADD COLUMN NOT NULL numa
    # tabela com linhas existentes (mesmo motivo de 0002/0003/0004). E
    # recusa CURRENT_TIMESTAMP especificamente em ADD COLUMN por não ser
    # constante ("Cannot add a column with non-constant default") — mesmo
    # sendo aceito em CREATE TABLE. Personagens já existentes ganham uma
    # data-placeholder; não afeta ordenação de personagens novos.
    op.add_column('personagens', sa.Column('criado_em', sa.DateTime(), nullable=False, server_default='2026-01-01 00:00:00'))
    # Etapa 8: "arquivar" em vez de apagar — a tela "Meus heróis" some com o
    # personagem sem destruir histórico/memória.
    op.add_column('personagens', sa.Column('arquivado', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('personagens', 'arquivado')
    op.drop_column('personagens', 'criado_em')
    op.drop_index(op.f('ix_usuarios_google_sub'), table_name='usuarios')
    op.drop_column('usuarios', 'google_sub')
    op.drop_column('usuarios', 'senha_hash')
