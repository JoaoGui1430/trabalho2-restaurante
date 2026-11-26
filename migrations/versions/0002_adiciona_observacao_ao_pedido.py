"""Adiciona observacao ao pedido

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Coluna opcional: os pedidos já existentes ficam com observacao nula.
    op.add_column(
        "pedido",
        sa.Column(
            "observacao",
            sqlmodel.sql.sqltypes.AutoString(length=300),
            nullable=True,
        ),
    )


def downgrade():
    # ALTER TABLE preserva as referências de itens e fechamentos no SQLite.
    # DROP COLUMN está disponível a partir do SQLite 3.35.
    op.drop_column("pedido", "observacao")
