"""Configuración de la aplicación cargada desde variables de entorno.

Nada de credenciales quemadas: todo viene del entorno (.env vía Docker Compose).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: str = "development"

    # ── Base de datos ────────────────────────────────────────
    postgres_user: str = "inventario"
    postgres_password: str = "inventario"
    postgres_db: str = "inventario"
    postgres_host: str = "db"
    postgres_port: int = 5432

    # ── API ──────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # ── Seguridad / JWT (Fase 1) ─────────────────────────────
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    admin_cedula: str = "1000000000"
    admin_password: str = "admin"
    admin_nombre: str = "Administrador"

    # Plantilla de demostración que siembra el seed (ver seed/usuarios_demo.py).
    # El interruptor existe porque son usuarios con clave conocida: si el sistema
    # deja de ser una demo, se apaga con SEED_USUARIOS_DEMO=false y no se siembran.
    seed_usuarios_demo: bool = True
    demo_password: str = "demo1234"

    # ── Reglas de negocio ────────────────────────────────────
    diff_umbral_pct: float = 10.0

    # ── ElevenLabs / audio (Fase 1) ──────────────────────────
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_stt_model_id: str = "scribe_v1"
    audio_dir: str = "/audio_store"

    # ── Dataset (seed) ───────────────────────────────────────
    dataset_path: str = "/dataset/inventory.json"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
