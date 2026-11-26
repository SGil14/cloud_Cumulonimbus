"""Configuración de la aplicación, leída desde variables de entorno o el archivo .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base de datos
    database_url: str

    # Fuente de datos: SAB / IDIGER
    sab_url: str = "https://app.sab.gov.co/sab/ServletTipoSensores"
    sab_timeout_segundos: float = 30
    cache_estaciones_segundos: int = 90

    # Geocodificación (buscador de destinos)
    ideca_api_key: str = ""  # gratuita, la entrega IDECA; sin ella se usa solo Nominatim
    ideca_url: str = "https://catalogopmb.catastrobogota.gov.co/PMBWeb/web/api"
    nominatim_user_agent: str = "cumulonimbus/0.1 (consulta de lluvia en Bogota)"
    geocoding_timeout_segundos: float = 15

    # Rutas (Valhalla, servicio gratuito de OpenStreetMap)
    ruta_url: str = "https://valhalla1.openstreetmap.de/route"
    ruta_timeout_segundos: float = 25

    # Reglas de negocio
    minutos_lectura_vieja: int = 30
    estaciones_cercanas: int = 3

    # Recolector del histórico
    recolector_activo: bool = True
    recolector_intervalo_minutos: int = 5

    # Autenticación (JWT). La llave NUNCA va en el código: se pasa por entorno o por Secret de Kubernetes.
    jwt_secret_key: str = ""  # mínimo 16 caracteres; sin ella el registro y el login responden 503
    jwt_expira_minutos: int = 60
    admin_correo: str = ""  # quien se registre con este correo recibe el rol administrador

    # (Opcional) dirección de Grafana: el panel de administración muestra un enlace si se define
    grafana_url: str = ""

    # API
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
