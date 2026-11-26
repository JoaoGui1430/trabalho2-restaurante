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
    with op.batch_alter_table("pedido") as batch_op:
        batch_op.add_column(
            sa.Column(
                "observacao",
                sqlmodel.sql.sqltypes.AutoString(length=300),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("pedido") as batch_op:
        batch_op.drop_column("observacao")
