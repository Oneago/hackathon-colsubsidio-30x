"""Esquemas Pydantic (contrato de la API).

ANTI-SESGO: los esquemas del canal MÓVIL (prefijo `Movil*`) NO contienen
`cantidad_erp`. El campo no existe en esas clases → no puede viajar al móvil.
Un test de contrato (tests/test_anti_sesgo.py) verifica esto sobre el OpenAPI.
"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    EstadoListado,
    EstadoToma,
    MetodoConteo,
    RolUsuario,
    TipoEntrada,
    UnidadMedida,
)


# ── Auth ─────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    cedula: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: RolUsuario
    nombre: str
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str = Field(min_length=6)


# ── Bodega ───────────────────────────────────────────────────
class BodegaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    id_erp: int | None
    nombre: str
    es_operativa: bool


# ── Usuario ──────────────────────────────────────────────────
class UsuarioCreate(BaseModel):
    nombre: str
    cedula: str
    password: str = Field(min_length=6)
    rol: RolUsuario
    bodega_ids: list[int] = Field(default_factory=list)


class UsuarioUpdate(BaseModel):
    nombre: str | None = None
    activo: bool | None = None
    bodega_ids: list[int] | None = None


class UsuarioResetPassword(BaseModel):
    """Restablecimiento hecho por el administrador: no exige la contraseña actual
    (el punto es justamente que el usuario la olvidó). La clave asignada es la
    definitiva; no obliga a rotarla al ingresar."""
    password_nueva: str = Field(min_length=6)


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    cedula: str
    rol: RolUsuario
    activo: bool
    must_change_password: bool
    bodegas: list[BodegaRead] = Field(default_factory=list)


class MeResponse(UsuarioRead):
    pass


# ── Item (canal WEB: incluye cantidad_erp) ──────────────────
class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nr_articulo: int | None
    codigo_barras: str
    descripcion: str
    unidad: UnidadMedida
    cantidad_erp: Decimal  # visible solo en web


# ── Toma de inventario ──────────────────────────────────────
class TomaCreate(BaseModel):
    bodega_id: int


class TomaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bodega_id: int
    estado: EstadoToma
    fecha_apertura: datetime
    fecha_cierre: datetime | None


# ── Listado de conteo (asignación) ──────────────────────────
class ListadoCreate(BaseModel):
    toma_id: int
    bodega_id: int
    supernumerario_id: int
    # Si es None/omitido, se incluyen todos los ítems DISPONIBLES de la bodega
    # (los no tomados por otro listado activo de esta toma).
    item_ids: list[int] | None = None


class ListadoUpdate(BaseModel):
    """Reasignar (supernumerario_id) y/o cambiar el estado (cancelar/completar)."""
    supernumerario_id: int | None = None
    estado: EstadoListado | None = None


class ListadoItemsAdd(BaseModel):
    """Agrega ítems a un listado activo. Solo agrega: no permite quitar ítems ya
    incluidos (ver `agregar_items_listado` en `routers/listados.py`)."""
    item_ids: list[int]


class ListadoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    toma_id: int
    bodega_id: int
    supernumerario_id: int | None
    # Denormalizados para la web: el supervisor NO puede listar /usuarios, así que
    # sin esto vería solo el id crudo del supernumerario.
    supernumerario_nombre: str | None = None
    bodega_nombre: str = ""
    estado: EstadoListado
    total_items: int = 0
    contados: int = 0


# ── Conteo (canal WEB / resultados) ─────────────────────────
class ConteoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    listado_item_id: int
    cantidad_contada: Decimal
    contado_por: int | None
    contado_en: datetime
    metodo: MetodoConteo
    entrada: TipoEntrada
    intento_num: int


# ── MÓVIL (SIN cantidad_erp) ────────────────────────────────
class MovilItem(BaseModel):
    """Ítem que ve el supernumerario. NO expone la cantidad del ERP."""
    listado_item_id: int
    item_id: int
    codigo_barras: str
    descripcion: str
    unidad: UnidadMedida
    unidad_texto: str
    frase_confirmacion: str
    audio_url: str | None
    contado: bool


class MovilListado(BaseModel):
    listado_id: int
    toma_id: int
    bodega_id: int
    bodega_nombre: str
    items: list[MovilItem]


class MovilConteoCreate(BaseModel):
    listado_item_id: int
    cantidad_contada: Decimal
    metodo: MetodoConteo
    entrada: TipoEntrada


class MovilConteoRead(BaseModel):
    id: int
    listado_item_id: int
    cantidad_contada: Decimal
    contado_en: datetime
    intento_num: int


class MovilDictadoRead(BaseModel):
    """Texto transcrito por ElevenLabs a partir del audio dictado por el supernumerario."""
    texto: str


# ── Comparación ERP vs. conteo (canal WEB, Fase 4) ──────────
class ComparacionFila(BaseModel):
    item_id: int
    codigo_barras: str
    descripcion: str
    unidad: UnidadMedida
    cantidad_erp: Decimal
    cantidad_contada: Decimal | None
    contado: bool
    diff_abs: Decimal | None
    diff_pct: float | None
    critico: bool
    contado_por: int | None
    contado_en: datetime | None
    metodo: MetodoConteo | None
    entrada: TipoEntrada | None


class ComparacionResumen(BaseModel):
    total_items: int
    contados: int
    pendientes: int
    criticos: int
    umbral_pct: float


class ComparacionResponse(BaseModel):
    toma_id: int
    bodega_id: int
    bodega_nombre: str
    estado: EstadoToma
    resumen: ComparacionResumen
    filas: list[ComparacionFila]
