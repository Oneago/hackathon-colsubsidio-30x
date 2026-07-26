"""aceptación del inventario por el supervisor

Cierra el ciclo de reconciliación: tras comparar ERP vs. conteo, el supervisor
o bien **acepta** el inventario (queda constancia de quién y cuándo) o bien
**solicita reconteo** (reabrir la toma, que ya existía).

Se modela con dos columnas nullable en `toma_inventario` y NO con un valor nuevo
del enum `estado_toma`: aceptar no es un estado del ciclo de conteo (la toma
sigue estando cerrada), es un sello de aprobación sobre una toma ya cerrada.
Además, `ALTER TYPE ... ADD VALUE` no corre dentro del bloque transaccional en
que Alembic ejecuta las migraciones, así que evitarlo es también lo práctico.

Revision ID: c8e1a52d7f04
Revises: b6f2a41c9d3e
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8e1a52d7f04'
down_revision: Union[str, None] = 'b6f2a41c9d3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'toma_inventario',
        sa.Column('aceptada_en', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'toma_inventario',
        sa.Column('aceptada_por', sa.Integer(), nullable=True),
    )
    # SET NULL y no CASCADE: si se borra el usuario, la toma sigue aceptada;
    # se pierde el "quién", no el hecho de que se aprobó.
    op.create_foreign_key(
        'fk_toma_inventario_aceptada_por_usuario',
        'toma_inventario', 'usuario',
        ['aceptada_por'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_toma_inventario_aceptada_por_usuario', 'toma_inventario', type_='foreignkey')
    op.drop_column('toma_inventario', 'aceptada_por')
    op.drop_column('toma_inventario', 'aceptada_en')
