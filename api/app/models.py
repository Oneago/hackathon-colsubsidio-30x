"""Modelo de datos del sistema de toma de inventarios.

Notas de diseño clave:
- `Item.cantidad_erp` es el campo ANTI-SESGO: se almacena, pero NUNCA debe
  serializarse hacia el móvil. La separación se hace a nivel de esquema Pydantic
  (Fase 1), no solo en la UI.
- Regla de roles: supernumerario = exactamente 1 bodega, supervisor = 1..N,
  administrador = todas. Se valida en modelo (constraints) y en la API.
- `ListadoConteo` usa un índice único parcial para impedir que la misma
  bodega/toma tenga más de un listado activo (bloqueo de concurrencia).
"""
import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# ── Enumeraciones ────────────────────────────────────────────
class RolUsuario(str, enum.Enum):
    administrador = "administrador"
    supervisor = "supervisor"
    supernumerario = "supernumerario"


class UnidadMedida(str, enum.Enum):
    unidad = "unidad"
    kilogramo = "kilogramo"
    litro = "litro"
    porcion = "porcion"


class EstadoToma(str, enum.Enum):
    abierta = "abierta"
    cerrada = "cerrada"


class EstadoListado(str, enum.Enum):
    activo = "activo"
    completado = "completado"
    cancelado = "cancelado"


class MetodoConteo(str, enum.Enum):
    escaneo = "escaneo"
    busqueda = "busqueda"


class TipoEntrada(str, enum.Enum):
    voz = "voz"
    manual = "manual"


class EstadoAudio(str, enum.Enum):
    pendiente = "pendiente"
    listo = "listo"
    error = "error"


# ── Mixin de timestamps ──────────────────────────────────────
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ── Asociación M:N usuario ↔ bodega ─────────────────────────
usuario_bodega = Table(
    "usuario_bodega",
    Base.metadata,
    Column("usuario_id", ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True),
    Column("bodega_id", ForeignKey("bodega.id", ondelete="CASCADE"), primary_key=True),
)


# ── Entidades ────────────────────────────────────────────────
class Bodega(TimestampMixin, Base):
    __tablename__ = "bodega"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_erp: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    # True para las bodegas que efectivamente cargan inventario (mapeadas al stock).
    es_operativa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    items: Mapped[list["Item"]] = relationship(back_populates="bodega", cascade="all, delete-orphan")
    usuarios: Mapped[list["Usuario"]] = relationship(secondary=usuario_bodega, back_populates="bodegas")


class Usuario(TimestampMixin, Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    cedula: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(SAEnum(RolUsuario, name="rol_usuario"), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    bodegas: Mapped[list["Bodega"]] = relationship(secondary=usuario_bodega, back_populates="usuarios")


class AudioAsset(TimestampMixin, Base):
    """Audio TTS pre-generado, deduplicado por descripción normalizada."""
    __tablename__ = "audio_asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hash_descripcion: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    creditos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ruta_mp3: Mapped[str | None] = mapped_column(String(512), nullable=True)
    estado: Mapped[EstadoAudio] = mapped_column(
        SAEnum(EstadoAudio, name="estado_audio"), default=EstadoAudio.pendiente, nullable=False
    )


class Item(TimestampMixin, Base):
    """Línea de stock de una bodega (SKU en una ubicación)."""
    __tablename__ = "item"
    __table_args__ = (
        UniqueConstraint("bodega_id", "codigo_barras", name="uq_item_bodega_codigo"),
        UniqueConstraint("bodega_id", "descripcion_norm", name="uq_item_bodega_desc"),
        Index("ix_item_bodega_desc", "bodega_id", "descripcion_norm"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bodega_id: Mapped[int] = mapped_column(ForeignKey("bodega.id", ondelete="CASCADE"), nullable=False)
    nr_articulo: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    codigo_barras: Mapped[str] = mapped_column(String(64), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion_norm: Mapped[str] = mapped_column(String(255), nullable=False)
    unidad: Mapped[UnidadMedida] = mapped_column(SAEnum(UnidadMedida, name="unidad_medida"), nullable=False)
    # Cantidad reportada por el ERP — ANTI-SESGO: nunca se expone al móvil.
    cantidad_erp: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    audio_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("audio_asset.id", ondelete="SET NULL"), nullable=True
    )

    bodega: Mapped["Bodega"] = relationship(back_populates="items")
    audio_asset: Mapped["AudioAsset | None"] = relationship()


class TomaInventario(TimestampMixin, Base):
    """Ciclo de conteo: agrupa los conteos de una bodega entre apertura y cierre."""
    __tablename__ = "toma_inventario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bodega_id: Mapped[int] = mapped_column(ForeignKey("bodega.id", ondelete="CASCADE"), nullable=False)
    estado: Mapped[EstadoToma] = mapped_column(
        SAEnum(EstadoToma, name="estado_toma"), default=EstadoToma.abierta, nullable=False
    )
    fecha_apertura: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creada_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)


class ListadoConteo(TimestampMixin, Base):
    """Asignación de conteo a un supernumerario dentro de una toma."""
    __tablename__ = "listado_conteo"
    __table_args__ = (
        # Bloqueo de concurrencia: una sola asignación ACTIVA por (toma, bodega).
        Index(
            "uq_listado_activo_toma_bodega",
            "toma_id",
            "bodega_id",
            unique=True,
            postgresql_where=text("estado = 'activo'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    toma_id: Mapped[int] = mapped_column(ForeignKey("toma_inventario.id", ondelete="CASCADE"), nullable=False)
    bodega_id: Mapped[int] = mapped_column(ForeignKey("bodega.id", ondelete="CASCADE"), nullable=False)
    supernumerario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True
    )
    estado: Mapped[EstadoListado] = mapped_column(
        SAEnum(EstadoListado, name="estado_listado"), default=EstadoListado.activo, nullable=False
    )
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)

    items: Mapped[list["ListadoItem"]] = relationship(
        back_populates="listado", cascade="all, delete-orphan"
    )


class ListadoItem(TimestampMixin, Base):
    """Ítem que pertenece a un listado de conteo."""
    __tablename__ = "listado_item"
    __table_args__ = (UniqueConstraint("listado_id", "item_id", name="uq_listado_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listado_id: Mapped[int] = mapped_column(ForeignKey("listado_conteo.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id", ondelete="CASCADE"), nullable=False)
    contado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    listado: Mapped["ListadoConteo"] = relationship(back_populates="items")
    item: Mapped["Item"] = relationship()


class Conteo(TimestampMixin, Base):
    """Registro de un conteo con trazabilidad. Recuento libre: varias filas por
    ítem mientras la toma esté abierta; vale el `intento_num` mayor (último)."""
    __tablename__ = "conteo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listado_item_id: Mapped[int] = mapped_column(
        ForeignKey("listado_item.id", ondelete="CASCADE"), nullable=False
    )
    cantidad_contada: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    contado_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    contado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    metodo: Mapped[MetodoConteo] = mapped_column(SAEnum(MetodoConteo, name="metodo_conteo"), nullable=False)
    entrada: Mapped[TipoEntrada] = mapped_column(SAEnum(TipoEntrada, name="tipo_entrada"), nullable=False)
    intento_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
