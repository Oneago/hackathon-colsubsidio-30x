"""cerrar listados activos que cuelgan de tomas ya cerradas

Solo datos: no cambia el esquema. Antes, `POST /tomas/{id}/cerrar` no tocaba los
listados, así que quedaron filas `estado='activo'` bajo tomas cerradas. Esas
filas hacían que el móvil entregara un listado muerto y que la validación de
"una asignación vigente por supernumerario" contara asignaciones inexistentes.
El cierre de toma ya las completa; esta migración normaliza lo que quedó atrás.

Revision ID: a1c7f4e29b30
Revises: e3d5b79fdb28
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c7f4e29b30'
down_revision: Union[str, None] = 'e3d5b79fdb28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE listado_conteo AS lc
           SET estado = 'completado',
               updated_at = now()
          FROM toma_inventario AS ti
         WHERE ti.id = lc.toma_id
           AND lc.estado = 'activo'
           AND ti.estado = 'cerrada'
        """
    )


def downgrade() -> None:
    # Irreversible a propósito: no se puede distinguir un listado completado por
    # esta migración de uno completado por el cierre normal de la toma.
    pass
