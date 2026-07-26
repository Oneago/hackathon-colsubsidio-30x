"""permitir listados activos en paralelo para la misma toma

El bloqueo de concurrencia pasa de "una asignación activa por (toma, bodega)"
a "sin ítems repetidos entre listados activos de una misma toma". Esa nueva
invariante no se expresa como índice único simple sobre `listado_conteo`
(exigiría denormalizar toma_id/estado en `listado_item`); se reemplaza por un
pg_advisory_xact_lock(toma_id) + chequeo de solape por ítem en
`routers/listados.py`.

Revision ID: b6f2a41c9d3e
Revises: a1c7f4e29b30
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b6f2a41c9d3e'
down_revision: Union[str, None] = 'a1c7f4e29b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('uq_listado_activo_toma_bodega', table_name='listado_conteo')


def downgrade() -> None:
    op.create_index(
        'uq_listado_activo_toma_bodega',
        'listado_conteo',
        ['toma_id', 'bodega_id'],
        unique=True,
        postgresql_where=sa.text("estado = 'activo'"),
    )
