"""Esquemas de la autenticación, los roles y los favoritos."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Rol = Literal["usuario", "administrador"]


class Credenciales(BaseModel):
    correo: EmailStr
    clave: str = Field(min_length=1, max_length=128)

    @field_validator("correo")
    @classmethod
    def _minusculas(cls, v: str) -> str:
        return v.lower()


class Registro(Credenciales):
    clave: str = Field(min_length=8, max_length=128)

    @field_validator("clave")
    @classmethod
    def _clave_decente(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("La contraseña debe tener al menos una letra y un número.")
        return v


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    correo: str
    rol: Rol
    creado_en: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expira_en_segundos: int
    usuario: UsuarioOut


class CambioRol(BaseModel):
    rol: Rol


class FavoritoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    texto: str = Field(min_length=2, max_length=300)

    @field_validator("nombre", "texto")
    @classmethod
    def _sin_espacios_sobrantes(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("No puede estar vacío.")
        return v


class FavoritoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    texto: str
    creado_en: datetime
