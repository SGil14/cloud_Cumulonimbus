"""Tablas de la base de datos."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Estacion(Base):
    """Catálogo de pluviómetros del SAB. Se actualiza en cada consulta."""

    __tablename__ = "estaciones"

    id_sensor: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    id_estacion: Mapped[int] = mapped_column(Integer)
    nombre: Mapped[str] = mapped_column(String(150))
    id_localidad: Mapped[int | None] = mapped_column(Integer)
    localidad: Mapped[str] = mapped_column(String(80), index=True)
    latitud: Mapped[float]
    longitud: Mapped[float]
    tecnologia: Mapped[str | None] = mapped_column(String(50))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Lectura(Base):
    """Histórico: una fila por estación y por hora de lectura (sin duplicados)."""

    __tablename__ = "lecturas"
    __table_args__ = (
        UniqueConstraint("id_sensor", "fecha_lectura", name="uq_lectura_sensor_fecha"),
        Index("ix_lecturas_fecha", "fecha_lectura"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_sensor: Mapped[int] = mapped_column(ForeignKey("estaciones.id_sensor"))
    fecha_lectura: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valor_5min: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    acumulado_dia: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    registrado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeoCache(Base):
    """Direcciones ya geocodificadas, para no repetir consultas a las APIs externas."""

    __tablename__ = "geocache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consulta_normalizada: Mapped[str] = mapped_column(String(300), unique=True)
    consulta_original: Mapped[str] = mapped_column(String(300))
    latitud: Mapped[float]
    longitud: Mapped[float]
    direccion: Mapped[str | None] = mapped_column(String(500))
    barrio: Mapped[str | None] = mapped_column(String(150))
    localidad: Mapped[str | None] = mapped_column(String(80))
    proveedor: Mapped[str] = mapped_column(String(30))
    aproximada: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    usos: Mapped[int] = mapped_column(Integer, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_uso: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Consulta(Base):
    """Registro de cada búsqueda de destino hecha en la app."""

    __tablename__ = "consultas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    texto: Mapped[str] = mapped_column(String(300))
    tipo: Mapped[str] = mapped_column(String(20))  # localidad | direccion | coordenadas
    encontrado: Mapped[bool] = mapped_column(Boolean)
    latitud: Mapped[float | None]
    longitud: Mapped[float | None]
    barrio: Mapped[str | None] = mapped_column(String(150))
    localidad: Mapped[str | None] = mapped_column(String(80))
    proveedor: Mapped[str | None] = mapped_column(String(30))
    lloviendo_cerca: Mapped[bool | None] = mapped_column(Boolean)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
